"""Module A with classes and functions."""


class ClassA:
    """A class from package A.

    Args:
        name: The name parameter.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def greet(self) -> str:
        """Return a greeting.

        Returns:
            A greeting string.
        """
        return f"Hello from {self._name}"


def function_a(value: int) -> str:
    """Convert an integer to a string.

    Args:
        value: The integer value.

    Returns:
        The string representation.
    """
    return str(value)
