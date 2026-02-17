"""Utility functions and helpers."""


def format_name(first: str, last: str) -> str:
    """Format a full name from first and last names.

    Args:
        first: The first name.
        last: The last name.

    Returns:
        The formatted full name.
    """
    return f"{first} {last}"


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a value between minimum and maximum.

    Args:
        value: The value to clamp.
        minimum: The minimum allowed value.
        maximum: The maximum allowed value.

    Returns:
        The clamped value.
    """
    return max(minimum, min(maximum, value))
