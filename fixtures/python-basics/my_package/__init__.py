"""My Package - A sample Python package for testing starlight-sphinx.

This package demonstrates various Python documentation features including
classes, functions, constants, and subpackages.
"""

from my_package.core import MyClass, helper_function, MY_CONSTANT
from my_package.exceptions import MyError

__all__ = ["MyClass", "helper_function", "MY_CONSTANT", "MyError"]
__version__ = "1.0.0"
