"""Security utilities for Clara.

Provides input sanitization and security controls.
"""

import html
import re


class InputSanitizer:
    """Sanitize user input to prevent injection attacks.

    Per SECURITY-GOVERNANCE.md, all user input must pass through this sanitizer.
    """

    # Maximum lengths for different input types
    MAX_MESSAGE_LENGTH = 10000
    MAX_PROMPT_LENGTH = 50000

    # Patterns that might indicate prompt injection attempts
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)",
        r"disregard\s+(previous|above|all)\s+(instructions?|prompts?)",
        r"forget\s+(previous|above|all)\s+(instructions?|prompts?)",
        r"new\s+instructions?:",
        r"system\s*:",
        r"\[system\]",
        r"<\|im_start\|>",
        r"<\|endoftext\|>",
    ]

    @classmethod
    def sanitize_message(cls, message: str) -> str:
        """Sanitize a user message.

        Args:
            message: The raw user message

        Returns:
            Sanitized message safe for use
        """
        if not message:
            return ""

        # Truncate to max length
        message = message[:cls.MAX_MESSAGE_LENGTH]

        # Strip leading/trailing whitespace
        message = message.strip()

        # Normalize unicode
        message = message.encode('utf-8', errors='ignore').decode('utf-8')

        return message

    @classmethod
    def sanitize_system_prompt(cls, prompt: str) -> str:
        """Sanitize a system prompt extracted from database.

        Args:
            prompt: The raw system prompt

        Returns:
            Sanitized prompt
        """
        if not prompt:
            return ""

        # Truncate to max length
        prompt = prompt[:cls.MAX_PROMPT_LENGTH]

        # Strip leading/trailing whitespace
        prompt = prompt.strip()

        # Normalize unicode
        prompt = prompt.encode('utf-8', errors='ignore').decode('utf-8')

        return prompt

    @classmethod
    def detect_injection_attempt(cls, text: str) -> bool:
        """Check if text contains potential prompt injection patterns.

        Args:
            text: The text to check

        Returns:
            True if injection patterns detected
        """
        text_lower = text.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False

    @classmethod
    def escape_html(cls, text: str) -> str:
        """Escape HTML entities in text.

        Args:
            text: The raw text

        Returns:
            HTML-escaped text
        """
        return html.escape(text)
