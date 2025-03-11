import libcst as cst
import pytest
from modernize_attrs import ModernizeAttrsCodemod
from libcst.codemod import CodemodContext


@pytest.fixture
def check():
    def inner(before: str, after: str) -> None:
        context = CodemodContext(filename="example.py")
        command = ModernizeAttrsCodemod(context)
        result = command.transform_module(cst.parse_module(before))
        assert result.code.rstrip() == after.rstrip()

    return inner


def test_move_type_to_annotation(check):
    before = """
import attr

@attr.s
class MyClass:
    x = attr.ib(type=int)
    y = attr.ib(type=str, default="hello")
"""

    after = """
from attrs import define, field

@define
class MyClass:
    x: int
    y: str = field(default="hello")
"""
    check(before, after)


def test_attrs_import(check):
    before = """
import attrs

@attrs.s
class MyClass:
    x = attrs.ib(type=int)
    y = attrs.ib(type=str, default="hello") 
"""

    after = """
from attrs import define, field

@define
class MyClass:
    x: int
    y: str = field(default="hello")
"""
    check(before, after)

def test_multiple_types(check):
    before = """
import attr
from typing import List, Optional

@attr.s
class MyClass:
    x = attr.ib(type=List[int])
    y = attr.ib(type=Optional[str], default=None)
"""

    after = """
from typing import List, Optional
from attrs import define, field

@define
class MyClass:
    x: List[int]
    y: Optional[str] = field(default=None)
"""
    check(before, after)


def test_existing_annotation_with_type(check):
    before = """
import attr

@attr.s
class MyClass:
    x: int = attr.ib(type=int)  # redundant type
"""

    after = """
from attrs import define, field

@define
class MyClass:
    x: int  # redundant type
"""
    check(before, after)


def test_preserve_other_arguments(check):
    before = """
import attr

@attr.s
class MyClass:
    x = attr.ib(type=int, default=0, validator=attr.validators.instance_of(int))
"""

    after = """
import attr
from attrs import define, field

@define
class MyClass:
    x: int = field(default=0, validator=attr.validators.instance_of(int))
"""
    check(before, after)


def test_skip_untyped_attrs(check):
    before = '''
import attr

@attr.s
class MyClass:
    x = attr.ib()  # no type hint
    y = attr.ib(type=str, default="hello")
'''

    # Should remain unchanged
    check(before, before)
