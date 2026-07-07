"""
api_client.py - Gemini API client wrapper with safety settings, exception wrapping, and logging.
"""
import asyncio
import time
import re
from google import genai
from google.genai import types
from google.genai.types import GenerateContentConfig
from google.genai.errors import APIError

from .exceptions import GeminiAPIError, TruncatedResponseError

class GeminiClient:
    def __init__(self, model: str, settings: dict, model_opts: dict, executor=None):
        self.model = model
        self.settings = settings
        self.model_opts = model_opts
        self.executor = executor
        self.client = genai.Client()

    async def call_genai(self, system: str, user: str | list, logger, temperature: float = None) -> str:
        temp = temperature if temperature is not None else self.model_opts['temperature']
        top_p = self.model_opts['top_p']
        
        use_async = self.settings['features'].get('use_async_client', True)

        logger.debug("==================== API CALL START ====================")
        logger.debug(f"Model: {self.model} | Temperature: {temp} | Top_P: {top_p}")
        logger.debug(f"System Instruction:\n{system}")
        if isinstance(user, list):
            logger.debug("User Contents (Multi-turn):")
            for item in user:
                role = item.get("role", "unknown")
                text = ""
                if "parts" in item and item["parts"]:
                    text = item["parts"][0].get("text", "")
                logger.debug(f"  [{role}]: {text}")
        else:
            logger.debug(f"User Content:\n{user}")

        safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]

        t_start = time.time()
        try:
            if use_async:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=GenerateContentConfig(
                        system_instruction=system,
                        temperature=temp,
                        top_p=top_p,
                        safety_settings=safety_settings,
                    )
                )
            else:
                # Wrap synchronous generate_content in run_in_executor
                response = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self.client.models.generate_content,
                    self.model,
                    user,
                    GenerateContentConfig(
                        system_instruction=system,
                        temperature=temp,
                        top_p=top_p,
                        safety_settings=safety_settings,
                    )
                )
            latency = time.time() - t_start
            logger.debug(f"API Call finished in {latency:.2f}s")
        except APIError as e:
            logger.error(f"Gemini API Error: {e} | Code: {getattr(e, 'code', None)}")
            raise GeminiAPIError(f"Gemini API Error: {e}", status_code=getattr(e, 'code', None))
        except Exception as e:
            err_msg = str(e).lower()
            logger.error(f"Unexpected API Exception: {e}")
            if "timeout" in err_msg or "time out" in err_msg or "deadline" in err_msg:
                raise GeminiAPIError(f"Timeout: {e}", status_code=408)
            raise GeminiAPIError(f"Connection/Unexpected Error: {e}")

        raw = response.text or ""
        logger.debug(f"Raw response output:\n{raw}")

        # Strip thinking tags (if any)
        if self.settings['features'].get('clean_thinking_tags', True):
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
            raw = re.sub(r'<\|.*?\|>',         '', raw, flags=re.DOTALL)

        # Check finish reason
        finish_reason = None
        if response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                finish_reason = str(candidate.finish_reason).upper()
            
            # Log safety ratings if blocked
            if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                logger.debug(f"Safety Ratings: {[str(r) for r in candidate.safety_ratings]}")

        logger.debug(f"Finish Reason: {finish_reason}")
        logger.debug("==================== API CALL END ====================")

        if finish_reason in ("MAX_TOKENS", "LENGTH"):
            raise TruncatedResponseError("Response was truncated because it reached the token limit.")

        return raw.strip()
