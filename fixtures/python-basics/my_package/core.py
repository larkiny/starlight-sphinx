"""Core module with primary classes and functions."""

MY_CONSTANT: int = 42
"""The answer to everything."""

TIMEOUT: float = 30.0
"""Default timeout in seconds."""


class MyClass:
    """A well-documented class.

    This class demonstrates various documentation features
    including constructors, methods, properties, and class attributes.

    Args:
        name: The name of the instance.
        value: An optional value.

    Example:
        >>> obj = MyClass("test")
        >>> obj.name
        'test'
    """

    default_timeout: int = 30
    """Default timeout in seconds."""

    def __init__(self, name: str, value: int = 0) -> None:
        self._name = name
        self._value = value

    def do_something(self, param: str) -> bool:
        """Do something interesting.

        Args:
            param: The parameter to process.

        Returns:
            Whether the operation succeeded.

        Raises:
            ValueError: If param is empty.
        """
        if not param:
            raise ValueError("param cannot be empty")
        return True

    @property
    def name(self) -> str:
        """The name of this instance."""
        return self._name

    async def async_method(self) -> None:
        """An async method that does async things."""
        pass


class AnotherClass(MyClass):
    """Another class that extends MyClass.

    Args:
        name: The name of the instance.
        value: An optional value.
        extra: An extra parameter.
    """

    def __init__(self, name: str, value: int = 0, extra: str = "") -> None:
        super().__init__(name, value)
        self._extra = extra

    def another_method(self) -> str:
        """Return the extra value.

        Returns:
            The extra string value.
        """
        return self._extra


class DeprecatedClass:
    """An old class.

    .. deprecated:: 2.0
        Use :class:`MyClass` instead.
    """

    pass


def helper_function(x: int, y: int) -> int:
    """Add two numbers.

    Args:
        x: First number.
        y: Second number.

    Returns:
        The sum.
    """
    return x + y


def complex_function(
    data: list[str],
    *,
    verbose: bool = False,
    timeout: float = 30.0,
) -> dict[str, int]:
    """Process data with options.

    Args:
        data: List of strings to process.
        verbose: Enable verbose output.
        timeout: Operation timeout in seconds.

    Returns:
        A dictionary mapping strings to their lengths.

    Raises:
        ValueError: If data is empty.
        TimeoutError: If the operation times out.

    Example:
        >>> complex_function(["hello", "world"])
        {'hello': 5, 'world': 5}
    """
    if not data:
        raise ValueError("data cannot be empty")
    return {s: len(s) for s in data}
