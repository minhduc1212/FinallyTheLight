"""
exceptions.py - Custom exception classes for the translation pipeline.
"""

class TranslationError(Exception):
    """Base exception for translation errors."""
    pass


class GeminiAPIError(TranslationError):
    """Raised when the Gemini API returns an error."""
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class TruncatedResponseError(TranslationError):
    """Raised when response is truncated by the API due to token limits."""
    pass


class InvalidFormatError(TranslationError):
    """Raised when response format doesn't match expected XML tags."""
    pass


class DuplicateTranslationError(TranslationError):
    """Raised when the translation is detected as a duplicate of preceding content."""
    pass


class LazyTranslationError(TranslationError):
    """Raised when the translation matches original text too closely (lazy model behavior)."""
    pass
