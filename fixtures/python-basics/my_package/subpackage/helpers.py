"""Subpackage helper functions."""


def sub_helper(value: str) -> str:
    """Process a value in the subpackage.

    Args:
        value: The input string.

    Returns:
        The processed string.
    """
    return value.strip().lower()


class SubClass:
    """A class in the subpackage.

    Args:
        data: Initial data for the class.
    """

    def __init__(self, data: list[str]) -> None:
        self._data = data

    def process(self) -> list[str]:
        """Process the stored data.

        Returns:
            A list of processed strings.
        """
        return [sub_helper(item) for item in self._data]
