# modernize-attrs

A codemod to modernize your attrs usage by:
- Converting `@attr.s` and `@attrs.s` decorators to `@define`
- Moving type hints from `attr.ib(type=...)` to Python type annotations
- Converting `attr.ib()` to `attrs.field()`
- Removing empty `field()` calls when no other arguments are present

## Installation

```bash
pip install modernize-attrs
```

## Usage

You can run this codemod in two ways:

### 1. As a command-line tool

```bash
# Run on a single file
modernize-attrs path/to/your/file.py

# Run on a directory (will process all .py files recursively)
modernize-attrs path/to/your/directory

# Run with multiple paths
modernize-attrs path1.py path2.py directory1/
```

### 2. Using LibCST's CLI

```bash
python -m libcst.tool codemod modernize_attrs.ModernizeAttrsCodemod path/to/your/code
```

## Behavior

The codemod will:
- Convert code like this:
```python
import attr

@attr.s
class MyClass:
    x = attr.ib(type=int)
    y = attr.ib(type=str, default="hello")
```

Into:
```python
from attrs import define, field

@define
class MyClass:
    x: int
    y: str = field(default="hello")
```

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
git clone https://github.com/yourusername/modernize-attrs
cd modernize-attrs

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest
```
