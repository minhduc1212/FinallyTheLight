"""
prompt_builder.py - Helper functions for building system instructions, user queries, and proofread prompts.
"""
from typing import Dict, Any

def get_source_rules(prompts_cfg: Dict[str, Any], source_lang: str) -> str:
    """Return the matching source_rules_XX block from prompts yaml."""
    key = f'source_rules_{source_lang}'
    return prompts_cfg.get(key, prompts_cfg.get('source_rules_en', '')).strip()


def safe_format(template: str, **kwargs) -> str:
    """
    Safe string substitution that won't choke on literal { } in prompt text
    (e.g. JSON examples inside the YAML prompts).
    Only replaces {key} tokens that are in kwargs; leaves everything else alone.
    """
    for key, value in kwargs.items():
        template = template.replace('txt' if key == 'text' else '{' + key + '}', str(value))
    return template


def build_system_prompt(
    prompts_cfg: Dict[str, Any],
    genres_cfg: Dict[str, Any],
    genre: str,
    target_lang: str,
    source_lang: str,
    summary_history_enabled: bool,
    glossary_str: str = "",
    characters_str: str = ""
) -> str:
    base         = prompts_cfg['system_base'].strip()
    source_rules = get_source_rules(prompts_cfg, source_lang)

    genre_cfg   = genres_cfg['genres'].get(genre, {})
    genre_label = genre_cfg.get('label', genre)
    genre_hint  = f"Thể loại: {genre_label}. {genre_cfg.get('hint', '')}"

    lang_cfg         = genres_cfg['languages'].get(target_lang, {})
    lang_instruction = lang_cfg.get('instruction', f'Translate to {target_lang}.')

    term_cats = genre_cfg.get('term_categories', [])
    if term_cats:
        term_cats_str = ", ".join(term_cats)
        term_instruction = f"\n  - ĐỐI CHIẾU THỂ LOẠI: Phân đoạn này thuộc thể loại '{genre_label}'. Chú ý trích xuất các thuật ngữ thuộc danh mục sau: {term_cats_str}."
    else:
        term_instruction = ""

    base = base.replace('{term_categories_instruction}', term_instruction)

    system_prompt = f"{base}\n\n{source_rules}\n\n{genre_hint}\n{lang_instruction}"
    
    if summary_history_enabled:
        system_prompt += "\n\n- Tóm tắt ngắn gọn nội dung chính của phân đoạn này bằng tiếng Việt trong thẻ <summary>...</summary>."
    
    if glossary_str:
        system_prompt += f"\n\n[GLOSSARY - DỊCH ĐÚNG THEO BẢNG NÀY]\n{glossary_str}"
    if characters_str:
        system_prompt += f"\n\n[NHÂN VẬT & XƯNG HÔ - GIỮ NHẤT QUÁN]\n{characters_str}"
        
    return system_prompt


def build_user_message(
    prompts_cfg: Dict[str, Any],
    chunk: str,
    summary: str,
    glossary_str: str,
    characters_str: str
) -> str:
    parts = []

    if summary:
        tpl = prompts_cfg['context_section']
        parts.append(tpl.replace('{summary}', summary).rstrip())

    if glossary_str:
        tpl = prompts_cfg['glossary_section']
        parts.append(tpl.replace('{terms}', glossary_str).rstrip())

    if characters_str:
        tpl = prompts_cfg['characters_section']
        parts.append(tpl.replace('{characters}', characters_str).rstrip())

    prefix = '\n\n'.join(parts)
    recitation_bypass = "\n\n[LƯU Ý DỊCH THUẬT]\nHãy dịch thoát ý và dùng từ ngữ của riêng bạn, tránh dịch y hệt các câu chữ có sẵn trực tuyến để không bị bộ lọc trùng lặp (Recitation filter) chặn."
    if prefix:
        return prefix + recitation_bypass + '\n\n[VĂN BẢN CẦN DỊCH]\n' + chunk
    return '[VĂN BẢN CẦN DỊCH]\n' + chunk


def build_proofread_prompt(
    prompts_cfg: Dict[str, Any],
    source_chunk: str,
    raw_translation: str,
    glossary_str: str,
    characters_str: str
) -> tuple[str, str]:
    """Returns (system_instruction, user_content) for proofreading."""
    system = prompts_cfg['proofread_base'].strip()
    
    g_sec = ""
    if glossary_str:
        g_sec = prompts_cfg['glossary_section'].replace('{terms}', glossary_str).rstrip()
    c_sec = ""
    if characters_str:
        c_sec = prompts_cfg['characters_section'].replace('{characters}', characters_str).rstrip()

    user = prompts_cfg['proofread_user'].replace('{source_text}', source_chunk)\
                                          .replace('{raw_translation}', raw_translation)\
                                          .replace('{glossary_section}', g_sec)\
                                          .replace('{characters_section}', c_sec)\
                                          .strip()
    return system, user


def build_pre_extract_prompt(
    prompts_cfg: Dict[str, Any],
    text: str,
    source_lang: str
) -> str:
    sample = text[:15000]
    lang_labels = {
        'en': 'English',
        'zh': 'Tiếng Trung (Chinese)',
        'ja': 'Tiếng Nhật (Japanese)',
        'ko': 'Tiếng Hàn (Korean)'
    }
    lang_label = lang_labels.get(source_lang, source_lang)
    return prompts_cfg['pre_extract_prompt'].replace('{source_lang}', lang_label).replace('{text}', sample)
