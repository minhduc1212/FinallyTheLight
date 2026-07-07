"""
pipeline.py - Orchestrator for the translation pipeline.
Coordinates chunking, history-building, parallel/sequential translation execution, checkpointing, and output assembly.
"""

import asyncio
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn
import json
import logging
import os
import re
import time
import contextvars
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import yaml
import dotenv

from .chunker import chunk_text, get_chunk_stats, estimate_tokens, detect_script, get_chars_per_token
from .checkpoint_manager import CheckpointManager
from .glossary_manager import GlossaryManager
from .lang_detector import detect_source_language, get_source_lang_label

# Modular helper imports
from .exceptions import (
    TranslationError,
    GeminiAPIError,
    TruncatedResponseError,
    InvalidFormatError,
    DuplicateTranslationError,
    LazyTranslationError,
)
from .similarity import calculate_tfidf_cosine_similarity
from .xml_parser import (
    parse_xml_output_only,
    parse_summary_output,
    parse_glossary_output,
    parse_proofread_output_only,
)
from .prompt_builder import (
    build_system_prompt,
    build_user_message,
    build_proofread_prompt,
    build_pre_extract_prompt,
)
from .api_client import GeminiClient

dotenv.load_dotenv()

current_file_stem = contextvars.ContextVar('current_file_stem', default='default')


class TranslationPipeline:
    def __init__(
        self,
        project: str,
        model: Optional[str] = None,
        genre: Optional[str] = None,
        target_lang: Optional[str] = None,
        source_lang: Optional[str] = None,   # override auto-detect
        output_dir: Optional[str] = None,
        chunk_size: Optional[int] = None,
        max_workers: Optional[int] = None,
    ):
        # Load configs
        self.settings  = self._load_yaml('config/settings.yaml')
        self.genres_cfg = self._load_yaml('config/genres.yaml')
        self.prompts   = self._load_yaml('prompts/system_prompts.yaml')

        # Override with explicit args
        self.model       = model       or self.settings['model']['name']
        self.genre       = genre       or self.settings['translation']['genre']
        self.target_lang = target_lang or self.settings['translation']['target_language']
        self.chunk_size  = chunk_size  or self.settings['translation']['chunk_size']
        self.max_workers = max_workers or self.settings['translation']['max_workers']
        self.project     = project

        self.console = Console()
        original_rich_print = self.console.print
        # Override print to handle Windows console encoding issues safely
        import sys
        def safe_rich_print(*args, **kwargs):
            try:
                original_rich_print(*args, **kwargs)
            except Exception:
                try:
                    with self.console.capture() as capture:
                        original_rich_print(*args, **kwargs)
                    text = capture.get()
                    encoding = sys.stdout.encoding or 'utf-8'
                    sys.stdout.write(text.encode(encoding, errors='replace').decode(encoding))
                    sys.stdout.flush()
                except Exception:
                    pass
        self.console.print = safe_rich_print
        self.loggers = {}
        
        # Initialize default logger
        self._get_logger('default')

        self.logger.info("--- Pipeline Initialized ---")
        self.logger.info(f"Project: {project} | Genre: {self.genre} | Target Lang: {self.target_lang} | Model: {self.model}")

        # source_lang: 'auto' means detect per-file; explicit value overrides
        self._source_lang_override = source_lang  # None or explicit code
        self.source_lang = source_lang or 'auto'  # shown in header

        self.output_dir = Path(output_dir or self.settings['paths']['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.checkpoint_mgr = CheckpointManager(project, base_dir=self.settings['paths'].get('checkpoint_dir', 'checkpoints'))
        self.glossary_mgr   = GlossaryManager(project, base_dir=self.settings['paths'].get('glossary_dir', 'data'))

        # Concurrency settings
        concurrency_cfg = self.settings.get('concurrency', {})
        self.use_global_semaphore = concurrency_cfg.get('use_global_semaphore', True)
        self.max_concurrent_requests = concurrency_cfg.get('max_concurrent_requests', self.max_workers)

        if max_workers is not None:
            self.max_concurrent_requests = max_workers
            self.max_workers = max_workers

        # Thread pool for blocking API calls (ensure it has at least max_concurrent_requests size)
        executor_size = max(self.max_concurrent_requests, self.max_workers)
        self.executor = ThreadPoolExecutor(max_workers=executor_size)

        self.global_semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        # Retry settings
        retry_cfg = self.settings.get('retry', {})
        self.max_retries = retry_cfg.get('max_retries', 5)
        self.initial_delay = retry_cfg.get('initial_delay', 2.0)
        self.exponential_base = retry_cfg.get('exponential_base', 2.0)
        self.max_delay = retry_cfg.get('max_delay', 60.0)
        self.jitter = retry_cfg.get('jitter', True)

        # API config options
        self.model_opts = {
            'temperature': self.settings['model'].get('temperature', 0.25),
            'top_p':       self.settings['model'].get('top_p', 0.9),
        }

        # Initialize API client helper
        if not os.environ.get("GEMINI_API_KEY"):
            raise ValueError(
                "❌ Environment variable GEMINI_API_KEY is not set.\n"
                "   Please set it in your .env file or environment."
            )
        self.api_client = GeminiClient(self.model, self.settings, self.model_opts, self.executor)

    @property
    def logger(self):
        stem = current_file_stem.get()
        return self._get_logger(stem)

    def _get_logger(self, file_stem: str):
        if file_stem not in self.loggers:
            # We want logs to be in logs/{project}/{file_stem}.log
            log_dir = Path("logs") / self.project
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{file_stem}.log"
            
            logger = logging.getLogger(f"{self.project}_{file_stem}")
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                fh = logging.FileHandler(log_file, encoding='utf-8')
                fh.setLevel(logging.DEBUG)
                formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                fh.setFormatter(formatter)
                logger.addHandler(fh)
            self.loggers[file_stem] = logger
        return self.loggers[file_stem]

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _load_yaml(path: str) -> dict:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    # ------------------------------------------------------------------
    # Source language helpers
    # ------------------------------------------------------------------
    def _resolve_source_lang(self, text: str) -> str:
        """Return explicit override, or auto-detect from text."""
        if self._source_lang_override:
            return self._source_lang_override
        return detect_source_language(text)

    def _sanitize_sensitive_words(self, text: str) -> str:
        """Obfuscates highly sensitive trigger words from raw input if configured."""
        sensitive_cfg = self.settings.get('sensitive_words', {})
        if not sensitive_cfg.get('enabled', False):
            return text
            
        words = sensitive_cfg.get('words', [])
        for word in words:
            if word in text:
                obfuscated = word[0] + '*' * (len(word) - 1)
                text = text.replace(word, obfuscated)
        return text

    async def _write_incremental_output(self, input_path: Path, translated_chunks: dict[int, str], failed_chunks: dict[int, str], total: int) -> None:
        final_parts = []
        for i in range(total):
            if i in translated_chunks:
                final_parts.append(translated_chunks[i])
            elif i in failed_chunks:
                final_parts.append(f"\n[LỖI DỊCH CHUNK {i+1}: {failed_chunks[i]}]\n")
            else:
                final_parts.append(f"\n[... Đang chờ dịch phân đoạn {i+1}/{total} ...]\n")
        
        final_text  = '\n\n'.join(final_parts)
        lang_suffix = f"_{self.target_lang}"
        output_path = self.output_dir / f"{input_path.stem}{lang_suffix}{input_path.suffix}"
        await self._write_text_file(output_path, final_text)

    async def _run_api_task(self, coro_func, *args, **kwargs):
        """Awaits an async API function, guarded by the global semaphore if enabled."""
        if self.use_global_semaphore:
            async with self.global_semaphore:
                return await coro_func(*args, **kwargs)
        else:
            return await coro_func(*args, **kwargs)

    # ------------------------------------------------------------------
    # Translation core functions
    # ------------------------------------------------------------------
    def _build_multi_turn_contents(
        self,
        chunk: str,
        context_snippet: str,
        glossary_str: str,
        characters_str: str,
        source_lang: str,
        idx: int,
        chunks: list[str],
        translated_chunks: dict[int, str],
        cpt: float,
    ) -> list[dict]:
        system_prompt = build_system_prompt(
            self.prompts,
            self.genres_cfg,
            self.genre,
            self.target_lang,
            source_lang,
            self.settings['features'].get('summary_history', False),
            glossary_str,
            characters_str
        )
        system_tokens = estimate_tokens(system_prompt, cpt)

        inject_in_system = self.settings['features'].get('inject_glossary_in_system_prompt', True)
        if inject_in_system:
            current_user_msg = build_user_message(self.prompts, chunk, context_snippet, "", "")
        else:
            current_user_msg = build_user_message(self.prompts, chunk, context_snippet, glossary_str, characters_str)

        current_tokens = estimate_tokens(current_user_msg, cpt)

        budget = self.settings['translation'].get('history_token_budget', 4000)
        max_history_chunks = self.settings['translation'].get('history_chapters', 2)

        history_pairs = []
        for prev_idx in range(idx - 1, -1, -1):
            if len(history_pairs) >= max_history_chunks:
                break
            if prev_idx in translated_chunks:
                history_pairs.append((chunks[prev_idx], translated_chunks[prev_idx]))

        history_pairs.reverse()

        valid_pairs = []
        current_history_tokens = 0

        for src, trans in reversed(history_pairs):
            user_text = f"[VĂN BẢN CẦN DỊCH]\n{src}"
            model_text = f"<translation>\n{trans}\n</translation>"
            pair_tokens = estimate_tokens(user_text, cpt) + estimate_tokens(model_text, cpt)
            if current_history_tokens + pair_tokens <= budget:
                valid_pairs.append((user_text, model_text))
                current_history_tokens += pair_tokens
            else:
                break

        valid_pairs.reverse()

        contents = []
        for user_text, model_text in valid_pairs:
            contents.append({"role": "user", "parts": [{"text": user_text}]})
            contents.append({"role": "model", "parts": [{"text": model_text}]})

        contents.append({"role": "user", "parts": [{"text": current_user_msg}]})
        return contents

    async def _translate_chunk(
        self,
        chunk: str,
        summary: str,
        glossary_str: str,
        characters_str: str,
        source_lang: str,
        contents: list = None,
        retry_instruction: str = None,
        temperature: float = None,
    ) -> str:
        inject_in_system = self.settings['features'].get('inject_glossary_in_system_prompt', True)
        
        sys_glossary = glossary_str if inject_in_system else ""
        sys_chars = characters_str if inject_in_system else ""
        system = build_system_prompt(
            self.prompts,
            self.genres_cfg,
            self.genre,
            self.target_lang,
            source_lang,
            self.settings['features'].get('summary_history', False),
            sys_glossary,
            sys_chars
        )

        if retry_instruction:
            system += f"\n\n[LƯU Ý QUAN TRỌNG - THỬ LẠI]\n{retry_instruction}"

        if contents:
            user = contents
            if retry_instruction:
                import copy
                user = copy.deepcopy(contents)
                user[-1]["parts"][0]["text"] += f"\n\n[LƯU Ý QUAN TRỌNG - THỬ LẠI]\n{retry_instruction}"
        else:
            user_glossary = "" if inject_in_system else glossary_str
            user_chars = "" if inject_in_system else characters_str
            user = build_user_message(
                self.prompts,
                chunk,
                summary,
                user_glossary,
                user_chars
            )
        return await self.api_client.call_genai(system, user, self.logger, temperature=temperature)

    async def _sleep_with_backoff(self, retry_count: int):
        delay = self.initial_delay * (self.exponential_base ** (retry_count - 1))
        delay = min(delay, self.max_delay)
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)
        await asyncio.sleep(delay)

    def _split_chunk_in_half(self, chunk: str, source_lang: str) -> list[str]:
        # Split by paragraph first
        paragraphs = chunk.split('\n\n')
        if len(paragraphs) >= 2:
            mid = len(paragraphs) // 2
            part1 = '\n\n'.join(paragraphs[:mid])
            part2 = '\n\n'.join(paragraphs[mid:])
            return [part1, part2]
        
        # If only one paragraph, split by sentence
        endings = re.compile(r'(?<=[.!?。！？…])\s*')
        sentences = [s for s in endings.split(chunk) if s.strip()]
        if len(sentences) >= 2:
            mid = len(sentences) // 2
            part1 = ' '.join(sentences[:mid])
            part2 = ' '.join(sentences[mid:])
            return [part1, part2]
            
        # Fallback: split by character count
        mid = len(chunk) // 2
        return [chunk[:mid], chunk[mid:]]

    async def _split_and_translate_chunk(
        self,
        chunk: str,
        context_snippet: str,
        glossary_str: str,
        characters_str: str,
        source_lang: str,
        chunk_idx: int,
        max_depth: int,
        contents: list = None,
        chunks: list[str] = None,
        translated_chunks: dict[int, str] = None,
    ) -> tuple[str, str]:
        parts = self._split_chunk_in_half(chunk, source_lang)
        
        inject_in_system = self.settings['features'].get('inject_glossary_in_system_prompt', True)
        
        contents_1 = None
        if contents:
            import copy
            contents_1 = copy.deepcopy(contents)
            user_msg_1 = build_user_message(self.prompts, parts[0], context_snippet, "", "") if inject_in_system else build_user_message(self.prompts, parts[0], context_snippet, glossary_str, characters_str)
            contents_1[-1]["parts"][0]["text"] = user_msg_1

        # Translate part 1
        t1, s1 = await self._translate_chunk_with_retry(
            parts[0], context_snippet, glossary_str, characters_str, source_lang, chunk_idx, max_depth=max_depth, contents=contents_1, chunks=chunks, translated_chunks=translated_chunks
        )
        
        # The context snippet for part 2 is the end of part 1's source text
        context_snippet_2 = parts[0][-1000:]
        
        contents_2 = None
        if contents:
            import copy
            contents_2 = copy.deepcopy(contents)
            user_msg_2 = build_user_message(self.prompts, parts[1], context_snippet_2, "", "") if inject_in_system else build_user_message(self.prompts, parts[1], context_snippet_2, glossary_str, characters_str)
            contents_2[-1]["parts"][0]["text"] = user_msg_2
        
        # Translate part 2
        t2, s2 = await self._translate_chunk_with_retry(
            parts[1], context_snippet_2, glossary_str, characters_str, source_lang, chunk_idx, max_depth=max_depth, contents=contents_2, chunks=chunks, translated_chunks=translated_chunks
        )
        
        combined_s = s1 + ("\n" + s2 if s2 else "") if s1 else s2
        return t1 + '\n\n' + t2, combined_s

    async def _translate_chunk_with_retry(
        self,
        chunk: str,
        context_snippet: str,
        glossary_str: str,
        characters_str: str,
        source_lang: str,
        chunk_idx: int,
        max_depth: int = 3,
        contents: list = None,
        chunks: list[str] = None,
        translated_chunks: dict[int, str] = None,
        temperature: float = None,
    ) -> tuple[str, str]:
        if hasattr(self, 'chunks_metadata'):
            if chunk_idx not in self.chunks_metadata:
                self.chunks_metadata[chunk_idx] = {
                    "try_count": 0,
                    "elapsed_time": 0.0,
                    "error": None
                }
        retries = 0
        current_chunk = chunk
        retry_instruction = None
        base_temp = temperature if temperature is not None else self.model_opts.get('temperature', 0.25)
        
        detect_dup = self.settings['features'].get('detect_duplicate_translation', True)
        dup_thresh = self.settings['translation'].get('duplicate_threshold', 0.85)
        lazy_thresh = self.settings['translation'].get('lazy_threshold', 0.75)
        lookback = self.settings['translation'].get('similarity_lookback', 2)

        total_chunks = len(chunks) if chunks else 1
        total_chunks_str = f"{total_chunks:03d}"

        while retries <= self.max_retries:
            if hasattr(self, 'chunks_metadata') and chunk_idx in self.chunks_metadata:
                self.chunks_metadata[chunk_idx]["try_count"] = retries + 1
            try:
                temp = base_temp
                if retries > 0:
                    temp = min(1.0, base_temp + 0.15 * retries)

                self.console.print(f"      [cyan]⏳ Chunk {chunk_idx+1:03d}/{total_chunks_str} - Translating (Try {retries+1})[/cyan]")
                self.logger.info(f"Chunk {chunk_idx+1}/{total_chunks_str} - Step 1/2: Translating & extracting glossary (attempt {retries+1})")
                self.logger.debug(f"Chunk {chunk_idx+1}/{total_chunks_str} - Context: {context_snippet[-100:] if len(context_snippet) > 100 else context_snippet}")

                raw_response = await self._run_api_task(
                    self._translate_chunk,
                    current_chunk,
                    context_snippet,
                    glossary_str,
                    characters_str,
                    source_lang,
                    contents,
                    retry_instruction,
                    temperature=temp,
                )
                
                self.logger.debug(f"Chunk {chunk_idx+1}/{total_chunks_str} - Raw response: {raw_response[:200]}...")

                # Check for empty response (likely Safety Block or Context Limit)
                if not raw_response.strip():
                    raise TruncatedResponseError("API returned an EMPTY string! For Gemma models, this often means the Context Length Limit was exceeded. Splitting chunk...")

                # Format check
                has_start = bool(re.search(r'<translation>', raw_response, re.IGNORECASE))
                has_end = bool(re.search(r'</translation>', raw_response, re.IGNORECASE))
                
                if has_start and not has_end:
                    raise TruncatedResponseError("Response was likely truncated before closing tag.")
                if not has_start:
                    raise InvalidFormatError("Response format is invalid (missing <translation> tags).")

                # Format check for glossary if auto_glossary is enabled
                auto_glossary_enabled = self.settings['features'].get('auto_glossary', True)
                if auto_glossary_enabled:
                    has_gl_start = re.search(r'<glossary>', raw_response, re.IGNORECASE)
                    has_gl_end = re.search(r'</glossary>', raw_response, re.IGNORECASE)
                    if not (has_gl_start and has_gl_end):
                        raise InvalidFormatError("Response format is invalid (missing <glossary> tags).")

                parsed_translation = parse_xml_output_only(raw_response)
                parsed_summary = parse_summary_output(raw_response) if self.settings['features'].get('summary_history', False) else ""
                
                if hasattr(self, 'chunks_metadata') and chunk_idx in self.chunks_metadata:
                    self.chunks_metadata[chunk_idx]["error"] = None

                # Extract glossary and update
                if auto_glossary_enabled:
                    glossary_data = parse_glossary_output(raw_response)
                    if glossary_data:
                        terms_added = await self._update_glossary_terms_async(glossary_data.get('terms', {}))
                        chars_added = await self._update_glossary_characters_async(glossary_data.get('characters', {}))
                        self.logger.info(f"Chunk {chunk_idx+1}/{total_chunks_str} - Extracted: {terms_added} terms, {chars_added} characters")
                        if terms_added > 0 or chars_added > 0:
                            if terms_added > 0:
                                self.console.print(f"      [dim]📝 Chunk {chunk_idx+1:03d}/{total_chunks_str} - Extracted {terms_added} terms[/dim]")
                            # Refresh glossary and characters strings for proofreading or similarity checks
                            filter_relevant = self.settings['features'].get('relevance_filtering', True)
                            glossary_str = self.glossary_mgr.format_terms_for_prompt(current_chunk if filter_relevant else None)
                            characters_str = self.glossary_mgr.format_characters_for_prompt(current_chunk if filter_relevant else None)

                # Editing and Proofreading
                editing_enabled = self.settings['features'].get('editing_and_proofreading', True)
                if editing_enabled and parsed_translation:
                    self.logger.info(f"Chunk {chunk_idx+1}/{total_chunks_str} - Step 2/2: Starting editing and proofreading")
                    parsed_translation = await self._proofread_chunk_with_retry(
                        current_chunk,
                        parsed_translation,
                        glossary_str,
                        characters_str,
                        source_lang,
                        chunk_idx,
                        total_chunks
                    )

                # Similarity checks
                if detect_dup and parsed_translation:
                    # 1. Lazy translation check (similarity between original chunk and translation)
                    if source_lang.lower() != self.target_lang.lower():
                        lazy_sim = calculate_tfidf_cosine_similarity(current_chunk, parsed_translation)
                        self.logger.info(f"Chunk {chunk_idx+1}/{total_chunks_str} - Lazy translation similarity: {lazy_sim:.4f}")
                        if lazy_sim > lazy_thresh:
                            raise LazyTranslationError(
                                f"Lazy translation detected: similarity {lazy_sim:.2f} exceeds threshold {lazy_thresh:.2f}"
                            )

                    # 2. Duplicate translation check (similarity between current translation and previous N translations)
                    if translated_chunks and chunk_idx is not None:
                        for prev_idx in range(chunk_idx - 1, max(-1, chunk_idx - lookback - 1), -1):
                            if prev_idx in translated_chunks:
                                prev_trans = translated_chunks[prev_idx]
                                dup_sim = calculate_tfidf_cosine_similarity(prev_trans, parsed_translation)
                                self.logger.info(f"Chunk {chunk_idx+1}/{total_chunks_str} - Duplicate similarity with chunk {prev_idx+1}: {dup_sim:.4f}")
                                if dup_sim > dup_thresh:
                                    raise DuplicateTranslationError(
                                        f"Duplicate translation detected with chunk {prev_idx+1}: "
                                        f"similarity {dup_sim:.2f} exceeds threshold {dup_thresh:.2f}"
                                    )

                return parsed_translation, parsed_summary
                
            except TruncatedResponseError as e:
                # Length truncation! Split and translate
                self.logger.warning(f"Chunk {chunk_idx+1}/{total_chunks_str} truncated. Splitting.")
                if max_depth > 0:
                    return await self._split_and_translate_chunk(
                        current_chunk, context_snippet, glossary_str, characters_str, source_lang, chunk_idx, max_depth - 1, contents, chunks, translated_chunks
                    )
                else:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - Max splitting depth reached.")
                    raise TranslationError("Max splitting depth reached, cannot translate chunk.")
                    
            except InvalidFormatError as e:
                if hasattr(self, 'chunks_metadata') and chunk_idx in self.chunks_metadata:
                    self.chunks_metadata[chunk_idx]["error"] = str(e)
                retries += 1
                if retries > self.max_retries:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - Format error: {e}. Max retries exceeded.")
                    raise
                self.console.print(f"      [bold yellow]⚠️  Chunk {chunk_idx+1:03d}/{total_chunks_str} - Format Error. Retrying ({retries}/{self.max_retries})[/bold yellow]")
                self.logger.warning(f"Chunk {chunk_idx+1}/{total_chunks_str} - Format error: {e}. Retrying ({retries}/{self.max_retries})")
                retry_instruction = "LƯU Ý: Phản hồi của bạn thiếu thẻ <translation>...</translation> hoặc <glossary>...</glossary>. Vui lòng trả về bản dịch được bọc chính xác trong thẻ này."
                await self._sleep_with_backoff(retries)
                
            except LazyTranslationError as e:
                if hasattr(self, 'chunks_metadata') and chunk_idx in self.chunks_metadata:
                    self.chunks_metadata[chunk_idx]["error"] = str(e)
                retries += 1
                if retries > self.max_retries:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - Lazy translation: {e}. Max retries exceeded.")
                    raise
                self.console.print(f"      [bold yellow]⚠️  Chunk {chunk_idx+1:03d}/{total_chunks_str} - Lazy translation. Retrying ({retries}/{self.max_retries})[/bold yellow]")
                self.logger.warning(f"Chunk {chunk_idx+1}/{total_chunks_str} - Lazy translation: {e}. Retrying ({retries}/{self.max_retries})")
                target_lang_label = get_source_lang_label(self.target_lang)
                retry_instruction = f"LƯU Ý: Bản dịch vừa rồi quá giống văn bản gốc (chưa được dịch). Hãy dịch hoàn chỉnh sang {target_lang_label}, không sao chép lại văn bản gốc."
                await self._sleep_with_backoff(retries)
  
            except DuplicateTranslationError as e:
                if hasattr(self, 'chunks_metadata') and chunk_idx in self.chunks_metadata:
                    self.chunks_metadata[chunk_idx]["error"] = str(e)
                retries += 1
                if retries > self.max_retries:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - Duplicate translation: {e}. Max retries exceeded.")
                    raise
                self.console.print(f"      [bold yellow]⚠️  Chunk {chunk_idx+1:03d}/{total_chunks_str} - Duplicate translation. Retrying ({retries}/{self.max_retries})[/bold yellow]")
                self.logger.warning(f"Chunk {chunk_idx+1}/{total_chunks_str} - Duplicate translation: {e}. Retrying ({retries}/{self.max_retries})")
                retry_instruction = "LƯU Ý: Bản dịch vừa rồi bị lặp lại hoặc quá giống phân đoạn trước. Vui lòng dịch đúng nội dung mới của phân đoạn này, không lặp lại câu chữ cũ."
                await self._sleep_with_backoff(retries)
  
            except GeminiAPIError as e:
                if hasattr(self, 'chunks_metadata') and chunk_idx in self.chunks_metadata:
                    self.chunks_metadata[chunk_idx]["error"] = str(e)
                is_retryable = e.status_code in (429, 408, 500, 502, 503, 504) or e.status_code is None
                if not is_retryable:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - Non-retryable Gemini API error: {e}")
                    raise
                
                retries += 1
                if retries > self.max_retries:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - Gemini API error: {e}. Max retries exceeded.")
                    raise
                
                self.console.print(f"      [bold red]⚠️  Chunk {chunk_idx+1:03d}/{total_chunks_str} - API Error ({e.status_code}). Retrying ({retries}/{self.max_retries})[/bold red]")
                self.logger.warning(f"Chunk {chunk_idx+1}/{total_chunks_str} - API error (status: {e.status_code}): {e}. Retrying ({retries}/{self.max_retries})")
                await self._sleep_with_backoff(retries)

    async def _pre_extract_glossary_and_characters(self, text: str, source_lang: str) -> dict:
        """Extract baseline glossary and characters from a text sample."""
        user = build_pre_extract_prompt(self.prompts, text, source_lang)
        try:
            raw = await self.api_client.call_genai("", user, self.logger, temperature=0.1)
            # Strip markdown code blocks if any
            clean_content = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', raw, flags=re.DOTALL)
            match = re.search(r'\{.*\}', clean_content, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            self.console.print(f"      [bold red]⚠️  Pre-extraction failed:[/bold red] {e}")
        return {}

    async def _proofread_chunk(
        self,
        source_chunk: str,
        raw_translation: str,
        glossary_str: str,
        characters_str: str,
        source_lang: str,
        temperature: float = None,
    ) -> str:
        system, user = build_proofread_prompt(
            self.prompts,
            source_chunk,
            raw_translation,
            glossary_str,
            characters_str
        )
        return await self.api_client.call_genai(system, user, self.logger, temperature=temperature)

    async def _proofread_chunk_with_retry(
        self,
        source_chunk: str,
        raw_translation: str,
        glossary_str: str,
        characters_str: str,
        source_lang: str,
        chunk_idx: int,
        total_chunks: int = 1,
    ) -> str:
        retries = 0
        base_temp = self.model_opts.get('temperature', 0.25)
        total_chunks_str = f"{total_chunks:03d}"
        
        while retries <= self.max_retries:
            try:
                temp = base_temp
                if retries > 0:
                    temp = min(1.0, base_temp + 0.15 * retries)
                    
                self.console.print(f"      [cyan]⏳ Chunk {chunk_idx+1:03d}/{total_chunks_str} - Proofreading (Try {retries+1})[/cyan]")
                self.logger.info(f"Chunk {chunk_idx+1}/{total_chunks_str} - Step 2/2: Editing & proofreading (attempt {retries+1})")

                raw_response = await self._run_api_task(
                    self._proofread_chunk,
                    source_chunk,
                    raw_translation,
                    glossary_str,
                    characters_str,
                    source_lang,
                    temperature=temp,
                )
                
                self.logger.debug(f"Chunk {chunk_idx+1}/{total_chunks_str} - Proofread response: {raw_response[:200]}...")

                # Format check
                has_start = re.search(r'<proofread>', raw_response, re.IGNORECASE)
                has_end = re.search(r'</proofread>', raw_response, re.IGNORECASE)
                if not (has_start and has_end):
                    raise InvalidFormatError("Proofread response format is invalid (missing <proofread> tags).")
                    
                parsed_proofread = parse_proofread_output_only(raw_response)
                self.logger.info(f"Chunk {chunk_idx+1}/{total_chunks_str} - Step 2/2: Proofreading success")
                return parsed_proofread
                
            except InvalidFormatError as e:
                retries += 1
                if retries > self.max_retries:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - Proofread format error: {e}. Max retries exceeded.")
                    raise
                self.console.print(f"      [bold yellow]⚠️  Chunk {chunk_idx+1:03d}/{total_chunks_str} - Format Error. Retrying ({retries}/{self.max_retries})[/bold yellow]")
                self.logger.warning(f"Chunk {chunk_idx+1}/{total_chunks_str} - Proofread format error: {e}. Retrying ({retries}/{self.max_retries})")
                await self._sleep_with_backoff(retries)
                
            except GeminiAPIError as e:
                is_retryable = e.status_code in (429, 408, 500, 502, 503, 504) or e.status_code is None
                if not is_retryable:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - Non-retryable API error during proofreading: {e}")
                    raise
                retries += 1
                if retries > self.max_retries:
                    self.logger.error(f"Chunk {chunk_idx+1}/{total_chunks_str} - API error during proofreading: {e}. Max retries exceeded.")
                    raise
                self.console.print(f"      [bold red]⚠️  Chunk {chunk_idx+1:03d}/{total_chunks_str} - API Error ({e.status_code}). Retrying ({retries}/{self.max_retries})[/bold red]")
                self.logger.warning(f"Chunk {chunk_idx+1}/{total_chunks_str} - Proofread API error (status: {e.status_code}): {e}. Retrying ({retries}/{self.max_retries})")
                await self._sleep_with_backoff(retries)

    # ------------------------------------------------------------------
    # Asynchronous File I/O helpers
    # ------------------------------------------------------------------
    async def _write_text_file(self, path: Path, text: str):
        """Write text to file in a non-blocking way using the executor."""
        await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: path.write_text(text, encoding='utf-8')
        )

    async def _save_checkpoint_async(self, stem: str, data: dict):
        """Saves checkpoint in executor."""
        await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.checkpoint_mgr.save,
            stem,
            data
        )

    async def _delete_checkpoint_async(self, stem: str):
        """Deletes checkpoint in executor."""
        await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.checkpoint_mgr.delete,
            stem
        )

    async def _update_glossary_terms_async(self, terms: dict) -> int:
        """Updates glossary terms in executor."""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.glossary_mgr.update_terms,
            terms
        )

    async def _update_glossary_characters_async(self, chars: dict) -> int:
        """Updates glossary characters in executor."""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.glossary_mgr.update_characters,
            chars
        )

    # ------------------------------------------------------------------
    # Core: translate one file
    # ------------------------------------------------------------------
    async def translate_file(self, input_path: Path, resume: bool = False, target_chunks: Optional[list[int]] = None) -> Path:
        # Set the context variable so logger logs to the correct file
        token = current_file_stem.set(input_path.stem)
        try:
            return await self._translate_file_internal(input_path, resume, target_chunks)
        finally:
            current_file_stem.reset(token)
            
    async def _translate_file_internal(self, input_path: Path, resume: bool = False, target_chunks: Optional[list[int]] = None) -> Path:
        loop = asyncio.get_event_loop()
        # Non-blocking file read
        text = await loop.run_in_executor(self.executor, input_path.read_text, 'utf-8')
        text = self._sanitize_sensitive_words(text)

        # ── Auto-detect source language ──────────────────────────────
        detected_lang = self._resolve_source_lang(text)
        lang_label    = get_source_lang_label(detected_lang)
        auto_marker   = '' if self._source_lang_override else ' (auto)'

        self.console.print(f"\n📖 [bold cyan] [{self.genre.upper()}] {input_path.name}")
        self.console.print(f"   🌐 Nguồn: {lang_label}{auto_marker} → {self.target_lang.upper()}")

        chunks = chunk_text(text, self.chunk_size, source_lang=detected_lang)
        stats  = get_chunk_stats(chunks, source_lang=detected_lang)
        total  = stats['total_chunks']

        # ── Save chunks for debugging ────────────────────────────────
        debug_chunks_dir = self.output_dir / "debug_chunks" / input_path.stem
        debug_chunks_dir.mkdir(parents=True, exist_ok=True)
        for idx, chunk_content in enumerate(chunks):
            chunk_file = debug_chunks_dir / f"chunk_{idx+1:03d}.txt"
            chunk_file.write_text(chunk_content, encoding='utf-8')

        self.logger.info(f"Starting translation of file: {input_path.name}")
        self.logger.info(f"Source Language: {lang_label}{auto_marker} | Target Language: {self.target_lang.upper()}")
        self.logger.info(f"Total Chunks: {total} | Chunks Stats: {stats}")

        self.console.print(f"   📦 [bold]{total}[/bold] chunks | avg {stats['avg_tokens']} tokens | "
              f"max {stats['max_tokens']} tokens")
        self.console.print(f"   💾 Saved {total} raw chunks to: {debug_chunks_dir}/")

        # ── Load Checkpoint ──────────────────────────────────────────────
        checkpoint = self.checkpoint_mgr.load(input_path.stem) if resume else None
        translated_chunks = {}
        summarized_chunks = {}
        failed_chunks = {}
        detected_lang = self._resolve_source_lang(chunks[0] if chunks else "")
        self.chunks_metadata = {}
        
        if checkpoint:
            self.console.print(f"\n[bold green]📂 Checkpoint found for '{input_path.stem}'. Resuming...")
            self.logger.info(f"Loaded checkpoint for {input_path.stem}")
            if 'translated_chunks' in checkpoint:
                for k, v in checkpoint['translated_chunks'].items():
                    if isinstance(v, str) and "[LỖI DỊCH CHUNK" in v:
                        failed_chunks[int(k)] = v
                    else:
                        translated_chunks[int(k)] = v
            if 'summarized_chunks' in checkpoint:
                for k, v in checkpoint['summarized_chunks'].items():
                    summarized_chunks[int(k)] = v
            if 'failed_chunks' in checkpoint:
                for k, v in checkpoint['failed_chunks'].items():
                    failed_chunks[int(k)] = v
            if 'chunks_metadata' in checkpoint:
                for k, v in checkpoint['chunks_metadata'].items():
                    self.chunks_metadata[int(k)] = v
            if checkpoint.get('glossary_terms'):
                await self._update_glossary_terms_async(checkpoint['glossary_terms'])
            if checkpoint.get('characters'):
                await self._update_glossary_characters_async(checkpoint['characters'])
            self.console.print(f"   ▶️  [yellow]Resuming progress: {len(translated_chunks)}/{total} chunks completed, {len(failed_chunks)} failed chunks")

        # ── Translate chunks in parallel ─────────────────────────────
        if target_chunks is not None:
            # Force retranslate of specific target chunks by removing them from cache
            for idx in target_chunks:
                translated_chunks.pop(idx, None)
                failed_chunks.pop(idx, None)
                self.chunks_metadata.pop(idx, None)
            chunks_to_translate = list(target_chunks)
        else:
            chunks_to_translate = [i for i in range(total) if i not in translated_chunks]
        
        if not chunks_to_translate and not failed_chunks:
            self.console.print(f"   [bold green]✅ All {total} chunks are already successfully translated. Skipping translation.[/bold green]")
            lang_suffix = f"_{self.target_lang}"
            output_path = self.output_dir / f"{input_path.stem}{lang_suffix}{input_path.suffix}"
            if not output_path.exists():
                final_parts = [translated_chunks.get(i, "") for i in range(total)]
                final_text  = '\n\n'.join(final_parts)
                await self._write_text_file(output_path, final_text)
            self.console.print(f"   [bold green]✨ Done → {output_path.name}")
            return output_path

        if chunks_to_translate:
            use_rolling_history = self.settings['features'].get('rolling_history', True)
            cpt = stats.get('chars_per_token', 3.5)
            if 'gemma' in self.model.lower():
                cpt = 1.0  # Gemma tokenizes CJK characters very inefficiently (approx 1 token per char)
            use_summary_history = self.settings['features'].get('summary_history', False)
            if use_rolling_history:
                limit_desc = "sequential with rolling history"
            elif use_summary_history:
                limit_desc = "sequential with summary history"
            else:
                limit_desc = f"global max: {self.max_concurrent_requests}" if self.use_global_semaphore else f"workers: {self.max_workers}"
                
            self.console.print(f"   [bold magenta]⚡ Translating {len(chunks_to_translate)} chunks ({limit_desc}) ...")
            
            local_semaphore = asyncio.Semaphore(self.max_workers) if (not self.use_global_semaphore and not use_rolling_history) else None
            filter_relevant = self.settings['features'].get('relevance_filtering', True)
            
            async def _translate_single_chunk(idx: int):
                async def _do_translation():
                    t_start = time.time()
                    chunk = chunks[idx]

                    # Context: last 1000 characters of previous original text, OR running summary
                    use_summary_history = self.settings['features'].get('summary_history', False)
                    if use_summary_history and idx > 0:
                        max_h = self.settings['translation'].get('history_chapters', 2)
                        h_sums = [summarized_chunks[p] for p in range(max(0, idx - max_h), idx) if p in summarized_chunks]
                        summary_text = "\n".join(h_sums) if h_sums else "(Chưa có tóm tắt)"
                        
                        last_trans = translated_chunks.get(idx - 1, "")
                        style_snippet = last_trans[-500:] if last_trans else ""
                        
                        context_snippet = f"TÓM TẮT CỐT TRUYỆN:\n{summary_text}"
                        if style_snippet:
                            context_snippet += f"\n\nĐOẠN DỊCH TRƯỚC ĐÓ (để tham khảo giọng văn):\n...{style_snippet}"
                    elif idx > 0:
                        prev_chunk = chunks[idx - 1]
                        context_snippet = prev_chunk[-1000:]
                    else:
                        context_snippet = "(Đây là phần đầu của tác phẩm, không có bối cảnh trước)"

                    # Dynamic glossary formatting per chunk
                    g_str = self.glossary_mgr.format_terms_for_prompt(chunk if filter_relevant else None)
                    c_str = self.glossary_mgr.format_characters_for_prompt(chunk if filter_relevant else None)

                    # Build multi-turn contents for rolling history
                    contents = None
                    if use_rolling_history:
                        contents = self._build_multi_turn_contents(
                            chunk,
                            context_snippet,
                            g_str,
                            c_str,
                            detected_lang,
                            idx,
                            chunks,
                            translated_chunks,
                            cpt,
                        )

                    try:
                        self.chunks_metadata[idx] = {
                            "try_count": self.chunks_metadata.get(idx, {}).get("try_count", 1),
                            "elapsed_time": 0.0,
                            "error": None
                        }
                        translation, summary = await self._translate_chunk_with_retry(
                            chunk,
                            context_snippet,
                            g_str,
                            c_str,
                            detected_lang,
                            idx,
                            contents=contents,
                            chunks=chunks,
                            translated_chunks=translated_chunks,
                        )
                        translated_chunks[idx] = translation
                        if self.settings['features'].get('summary_history', False):
                            summarized_chunks[idx] = summary

                        elapsed = time.time() - t_start
                        self.chunks_metadata[idx]["elapsed_time"] = round(elapsed, 2)
                        self.chunks_metadata[idx]["error"] = None

                        # Thread-safe save checkpoint (async)
                        await self._save_checkpoint_async(input_path.stem, {
                            'total_chunks': total,
                            'translated_chunks': {str(k): v for k, v in translated_chunks.items()},
                            'summarized_chunks': {str(k): v for k, v in summarized_chunks.items()},
                            'failed_chunks': {str(k): v for k, v in failed_chunks.items()},
                            'chunks_metadata': {str(k): v for k, v in self.chunks_metadata.items()},
                            'source_lang': detected_lang,
                            'glossary_terms': self.glossary_mgr.get_all(),
                            'characters': self.glossary_mgr.get_characters(),
                        })

                        # Update incremental output file
                        await self._write_incremental_output(input_path, translated_chunks, failed_chunks, total)

                        self.console.print(f"      [green]✅ Chunk {idx+1:03d}/{total} completed in {elapsed:.1f}s[/green]")
                        self.logger.info(f"Chunk {idx+1:03d}/{total} completed in {elapsed:.1f}s")
                    except Exception as e:
                        print(f"      ❌ Chunk {idx+1:03d}/{total} failed after all retries: {e}")
                        self.logger.error(f"Chunk {idx+1:03d}/{total} failed: {e}")
                        failed_chunks[idx] = str(e)
                        # Remove from translated_chunks if it was there
                        translated_chunks.pop(idx, None)
                        elapsed = time.time() - t_start
                        if idx not in self.chunks_metadata:
                            self.chunks_metadata[idx] = {"try_count": 1}
                        self.chunks_metadata[idx]["elapsed_time"] = round(elapsed, 2)
                        self.chunks_metadata[idx]["error"] = str(e)

                        await self._save_checkpoint_async(input_path.stem, {
                            'total_chunks': total,
                            'translated_chunks': {str(k): v for k, v in translated_chunks.items()},
                            'summarized_chunks': {str(k): v for k, v in summarized_chunks.items()},
                            'failed_chunks': {str(k): v for k, v in failed_chunks.items()},
                            'chunks_metadata': {str(k): v for k, v in self.chunks_metadata.items()},
                            'source_lang': detected_lang,
                            'glossary_terms': self.glossary_mgr.get_all(),
                            'characters': self.glossary_mgr.get_characters(),
                        })
                        await self._write_incremental_output(input_path, translated_chunks, failed_chunks, total)

                if local_semaphore:
                    async with local_semaphore:
                        await _do_translation()
                else:
                    await _do_translation()

            # Execute tasks
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=None),
                TaskProgressColumn(),
                TextColumn("[cyan]{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=self.console,
                expand=True
            )
            with progress:
                task_id = progress.add_task("Translating", total=len(chunks_to_translate))
                
                async def _translate_with_progress(idx):
                    await _translate_single_chunk(idx)
                    progress.advance(task_id)

                if use_rolling_history or self.settings['features'].get('summary_history', False):
                    for idx in chunks_to_translate:
                        await _translate_with_progress(idx)
                else:
                    tasks = [_translate_with_progress(idx) for idx in chunks_to_translate]
                    await asyncio.gather(*tasks)

            # ── Re-translate failed chunks ──────────────────────────────
            if failed_chunks:
                self.console.print(f"\n[bold red]🔄 Found {len(failed_chunks)}[/bold red] failed chunks. Starting re-translation phase...")
                self.logger.info(f"Starting re-translation phase for {len(failed_chunks)} failed chunks.")
                
                re_pass = 1
                max_re_passes = 3
                base_temp = self.model_opts.get('temperature', 0.25)
                while failed_chunks and re_pass <= max_re_passes:
                    self.console.print(f"   [bold yellow]🔄 Re-translation Pass {re_pass}/{max_re_passes}...")
                    self.logger.info(f"Re-translation Pass {re_pass}/{max_re_passes}")
                    
                    failed_indices = list(failed_chunks.keys())
                    for idx in failed_indices:
                        try:
                            t_start = time.time()
                            chunk = chunks[idx]

                            if use_summary_history and idx > 0:
                                max_h = self.settings['translation'].get('history_chapters', 2)
                                h_sums = [summarized_chunks[p] for p in range(max(0, idx - max_h), idx) if p in summarized_chunks]
                                summary_text = "\n".join(h_sums) if h_sums else "(Chưa có tóm tắt)"
                                
                                last_trans = translated_chunks.get(idx - 1, "")
                                style_snippet = last_trans[-500:] if last_trans else ""
                                
                                context_snippet = f"TÓM TẮT CỐT TRUYỆN:\n{summary_text}"
                                if style_snippet:
                                    context_snippet += f"\n\nĐOẠN DỊCH TRƯỚC ĐÓ (để tham khảo giọng văn):\n...{style_snippet}"
                            elif idx > 0:
                                prev_chunk = chunks[idx - 1]
                                context_snippet = prev_chunk[-1000:]
                            else:
                                context_snippet = "(Đây là phần đầu của tác phẩm, không có bối cảnh trước)"

                            g_str = self.glossary_mgr.format_terms_for_prompt(chunk if filter_relevant else None)
                            c_str = self.glossary_mgr.format_characters_for_prompt(chunk if filter_relevant else None)

                            contents = None
                            if use_rolling_history:
                                contents = self._build_multi_turn_contents(
                                    chunk,
                                    context_snippet,
                                    g_str,
                                    c_str,
                                    detected_lang,
                                    idx,
                                    chunks,
                                    translated_chunks,
                                    cpt,
                                )

                            translation, summary = await self._translate_chunk_with_retry(
                                chunk,
                                context_snippet,
                                g_str,
                                c_str,
                                detected_lang,
                                idx,
                                contents=contents,
                                chunks=chunks,
                                translated_chunks=translated_chunks,
                            )
                            
                            translated_chunks[idx] = translation
                            if self.settings['features'].get('summary_history', False):
                                summarized_chunks[idx] = summary
                            del failed_chunks[idx]

                            await self._save_checkpoint_async(input_path.stem, {
                                'total_chunks': total,
                                'translated_chunks': {str(k): v for k, v in translated_chunks.items()},
                                'summarized_chunks': {str(k): v for k, v in summarized_chunks.items()},
                                'failed_chunks': {str(k): v for k, v in failed_chunks.items()},
                                'source_lang': detected_lang,
                                'glossary_terms': self.glossary_mgr.get_all(),
                                'characters': self.glossary_mgr.get_characters(),
                            })

                            # Update incremental output file
                            await self._write_incremental_output(input_path, translated_chunks, failed_chunks, total)

                            elapsed = time.time() - t_start
                            self.console.print(f"      [green]✅ Chunk {idx+1:03d}/{total} re-translated in {elapsed:.1f}s[/green]")
                            self.logger.info(f"Chunk {idx+1:03d}/{total} successfully re-translated in {elapsed:.1f}s")
                        except Exception as e:
                            print(f"      ❌ Chunk {idx+1:03d}/{total} still failed on pass {re_pass}: {e}")
                            self.logger.error(f"Chunk {idx+1:03d}/{total} failed on pass {re_pass}: {e}")

                    re_pass += 1

        # ── Assemble & save output ───────────────────────────────────
        final_parts = []
        for i in range(total):
            if i in translated_chunks:
                final_parts.append(translated_chunks[i])
            elif i in failed_chunks:
                final_parts.append(f"\n[LỖI DỊCH CHUNK {i+1}: {failed_chunks[i]}]\n")
            else:
                final_parts.append(f"\n[... Đang chờ dịch phân đoạn {i+1}/{total} ...]\n")
        final_text  = '\n\n'.join(final_parts)
        lang_suffix = f"_{self.target_lang}"
        output_path = self.output_dir / f"{input_path.stem}{lang_suffix}{input_path.suffix}"
        
        await self._write_text_file(output_path, final_text)

        # Save glossary report
        report_path = self.output_dir / f"{self.project}_glossary_report.md"
        await self._write_text_file(report_path, self.glossary_mgr.export_report())

        # Explicitly save a status report file so the user can easily see what succeeded/failed
        status_file_path = self.output_dir / f"{input_path.stem}_status.json"
        
        # Build success and error list
        successful_ids = sorted([int(k)+1 for k in translated_chunks.keys() if k not in failed_chunks])
        error_dict = {f"Chunk {int(k)+1}": err for k, err in failed_chunks.items()}
        
        status_report = {
            "Total_Chunks": total,
            "Successful_Count": len(successful_ids),
            "Failed_Count": len(failed_chunks),
            "Failed_Chunks_Details": error_dict,
            "Successful_Chunks": successful_ids
        }
        
        # Always write the status report
        await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: status_file_path.write_text(json.dumps(status_report, ensure_ascii=False, indent=2), encoding='utf-8')
        )
        self.console.print(f"   [bold yellow]📝 Saved translation status report to: {status_file_path.name}[/bold yellow]")

        if failed_chunks:
            self.console.print(f"\n   [bold red]⚠️  WARNING: File completed with {len(failed_chunks)} failed chunks:")
            self.logger.warning(f"File completed with {len(failed_chunks)} failed chunks: {failed_chunks}")
            for k, err in failed_chunks.items():
                self.console.print(f"      [red]- Chunk {k+1}: {err}")

        # We keep the checkpoint instead of deleting it (even if successful), 
        # so that resume logic will see it's completely translated and won't restart from scratch.
        # It also preserves the state of any failed_chunks so --resume can retry them.
        await self._save_checkpoint_async(input_path.stem, {
            'total_chunks': total,
            'translated_chunks': {str(k): v for k, v in translated_chunks.items()},
            'summarized_chunks': {str(k): v for k, v in summarized_chunks.items()},
            'failed_chunks': {str(k): v for k, v in failed_chunks.items()},
            'source_lang': detected_lang,
            'glossary_terms': self.glossary_mgr.get_all(),
            'characters': self.glossary_mgr.get_characters(),
        })

        self.console.print(f"   [bold green]✨ Done → {output_path.name}")
        self.console.print(f"   [bold blue]📚 Glossary: {self.glossary_mgr.term_count()} terms | "
            f"👥 Characters: {self.glossary_mgr.char_count()} tracked")

        return output_path

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    async def run(self, input_path_str: str, resume: bool = False, target_chunks: Optional[list[int]] = None) -> None:
        input_path = Path(input_path_str)
        supported  = {'.txt', '.md'}

        if input_path.is_file():
            if input_path.suffix.lower() not in supported:
                self.console.print(f"[bold red]⚠️  Unsupported file type: {input_path.suffix}")
                return
            await self.translate_file(input_path, resume=resume, target_chunks=target_chunks)

        elif input_path.is_dir():
            if target_chunks is not None:
                self.console.print("[bold red]⚠️  --target-chunks / --fix-errors can only be used with a single input file, not a directory.[/bold red]")
                return
            files = []
            for ext in ['.txt', '.md']:
                files.extend(sorted(input_path.glob(f'*{ext}')))

            if not files:
                self.console.print("[bold red]⚠️  No .txt or .md files found in directory.")
                return

            if self.use_global_semaphore:
                self.console.print(f"\n[bold cyan]📁 Found {len(files)} files | global concurrency limit: {self.max_concurrent_requests}")
                local_semaphore = None
            else:
                self.console.print(f"\n[bold cyan]📁 Found {len(files)} files | {self.max_workers} parallel workers")
                local_semaphore = asyncio.Semaphore(self.max_workers)

            async def _translate_guarded(f: Path):
                if local_semaphore:
                    async with local_semaphore:
                        return await self.translate_file(f, resume=resume)
                else:
                    return await self.translate_file(f, resume=resume)

            results = await asyncio.gather(
                *[_translate_guarded(f) for f in files],
                return_exceptions=True,
            )

            for f, result in zip(files, results):
                if isinstance(result, Exception):
                    self.console.print(f"   [bold red]❌ FAILED: {f.name} → {result}")

        else:
            self.console.print(f"[bold red]❌ Path not found: {input_path}")
            return

        self.console.print(f"\n[bold green]🎉 All done![/bold green] Output in: {self.output_dir}/")
        self.executor.shutdown(wait=False)