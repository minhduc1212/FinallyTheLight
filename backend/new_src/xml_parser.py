"""
xml_parser.py - Parser helpers for extracting structured XML tags from API responses.
"""
import re
import json

def parse_xml_output_only(response_text: str) -> str:
    """Parses only the <translation> tag from the response."""
    translation_match = re.search(r'<translation>(.*?)</translation>', response_text, re.DOTALL | re.IGNORECASE)
    if translation_match:
        return translation_match.group(1).strip()
    # Fallback: remove XML tags if any, otherwise return raw
    return re.sub(r'<.*?>', '', response_text, flags=re.DOTALL).strip()


def parse_summary_output(raw_response: str) -> str:
    """Parse <summary> block."""
    match = re.search(r'<summary>(.*?)</summary>', raw_response, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def parse_glossary_output(response_text: str) -> dict:
    """Parses the <glossary> tag from the response and returns dict."""
    glossary_match = re.search(r'<glossary>(.*?)</glossary>', response_text, re.DOTALL | re.IGNORECASE)
    if glossary_match:
        content = glossary_match.group(1).strip()
        # Strip markdown code blocks if any
        clean_content = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', content, flags=re.DOTALL)
        match = re.search(r'\{.*\}', clean_content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception as e:
                # We can't log using self.logger here, so we raise or return empty dict
                # Caller will handle logging/error output if needed
                pass
    return {}


def parse_proofread_output_only(response_text: str) -> str:
    """Parses only the <proofread> tag from the response."""
    proofread_match = re.search(r'<proofread>(.*?)</proofread>', response_text, re.DOTALL | re.IGNORECASE)
    if proofread_match:
        return proofread_match.group(1).strip()
    # Fallback: remove XML tags if any, otherwise return raw
    return re.sub(r'<.*?>', '', response_text, flags=re.DOTALL).strip()
