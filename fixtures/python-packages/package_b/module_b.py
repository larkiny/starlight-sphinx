"""Module B with classes and functions."""

DEFAULT_VALUE: str = "default"
"""The default value used across module B."""


class ClassB:
    """A class from package B.

    Args:
        data: A list of strings.
    """

    def __init__(self, data: list[str]) -> None:
        self._data = data

    def count(self) -> int:
        """Count items in data.

        Returns:
            The number of items.
        """
        return len(self._data)


def function_b(items: list[str], separator: str = ", ") -> str:
    """Join items with a separator.

    Args:
        items: The items to join.
        separator: The separator string.

    Returns:
        The joined string.
    """
    return separator.join(items)
