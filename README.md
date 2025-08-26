# modernize-attrs

A codemod to modernize your attrs usage by:
- Converting `@attr.s` and `@attrs.s` decorators to `@define`
- Moving type hints from `attr.ib(type=...)` to Python type annotations
- Converting `attr.ib()` to `attrs.field()`
- Removing empty `field()` calls when no other arguments are present

## Usage

You can run the codemod without installing by using `uvx` or `pipx run`:
```bash
uvx git+https://github.com/jonathanberthias/modernize-attrs src_dir_or_file
```

## Behavior

The codemod will:
- Convert code like this:
```python
import attr

@attr.s
class MyClass:
    x = attr.ib(type=int, converter=int)
    y = attr.ib(type=str, default="hello")
```

Into:
```python
from attrs import define, field

@define
class MyClass:
    x: int = field(converter=int)
    y: str = "hello"
```

### Why?

The old way of using `attr.s` and `attr.ib` is now considered [outdated](https://www.attrs.org/en/stable/names.html).
The `attrs` library has introduced `@define` and `field()` to provide a more Pythonic way of defining classes with attributes, leveraging type hints for better clarity and tooling support.

In particular, only Mypy can understand the `type=` argument in `attr.ib()`, making it harder to use other type checkers or get pleasant IDE support.

### Safety Features

- The codemod will skip any class that contains `attr.ib()` calls without type hints and print a warning
- Existing type annotations are preserved
- Other `attr.ib()` arguments (like `default`, `validator`, etc.) are preserved in the `field()` call

## Requirements

- Python >= 3.11
- libcst >= 1.5.1

## Development

To set up for development:

```bash
# Clone the repository
git clone https://github.com/jonathanberthias/modernize-attrs
cd modernize-attrs

# Create a virtual environment and install dependencies
uv sync

# Run tests
uv run pytest
```
