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
    MAX_NAME_LENGTH = 200
    MAX_DESCRIPTION_LENGTH = 2000
    MAX_ARRAY_ITEMS = 50

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
    def sanitize_message(cls, message: str | None) -> str:
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
    def sanitize_system_prompt(cls, prompt: str | None) -> str:
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
    def sanitize_name(cls, name: str | None) -> str:
        """Sanitize a name (entity name, agent name, project name).

        Args:
            name: The raw name

        Returns:
            Sanitized name
        """
        if not name:
            return ""

        # Truncate to max length
        name = name[:cls.MAX_NAME_LENGTH]

        # Strip leading/trailing whitespace
        name = name.strip()

        # Normalize unicode
        name = name.encode('utf-8', errors='ignore').decode('utf-8')

        return name

    @classmethod
    def sanitize_description(cls, description: str | None) -> str:
        """Sanitize a description field.

        Args:
            description: The raw description

        Returns:
            Sanitized description
        """
        if not description:
            return ""

        # Truncate to max length
        description = description[:cls.MAX_DESCRIPTION_LENGTH]

        # Strip leading/trailing whitespace
        description = description.strip()

        # Normalize unicode
        description = description.encode('utf-8', errors='ignore').decode('utf-8')

        return description

    @classmethod
    def sanitize_array(cls, items: list | None, max_item_length: int = 500) -> list[str]:
        """Sanitize an array of strings.

        Args:
            items: The raw list of items
            max_item_length: Maximum length for each item

        Returns:
            Sanitized list with bounded size
        """
        if not items:
            return []

        # Limit number of items
        items = items[:cls.MAX_ARRAY_ITEMS]

        # Sanitize each item
        return [
            str(item)[:max_item_length].strip()
            for item in items
            if item
        ]

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
            text: The text to escape

        Returns:
            HTML-escaped text
        """
        return html.escape(text, quote=True)

    @classmethod
    def sanitize_template_value(cls, value: str | None) -> str:
        """Sanitize a value that will be inserted into a template.

        Prevents template injection by escaping special characters.

        Args:
            value: The raw value

        Returns:
            Sanitized value safe for template insertion
        """
        if not value:
            return ""

        # Truncate to reasonable length
        value = value[:cls.MAX_DESCRIPTION_LENGTH]

        # Strip whitespace
        value = value.strip()

        # Normalize unicode
        value = value.encode('utf-8', errors='ignore').decode('utf-8')

        # Don't allow template markers that could cause injection
        # Replace {{ and }} with escaped versions
        value = value.replace("{{", "{ {").replace("}}", "} }")

        return value
