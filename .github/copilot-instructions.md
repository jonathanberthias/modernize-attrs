# Copilot Instructions for modernize-attrs

## Project Overview
- **Purpose:** A codemod to modernize usage of the `attrs` library in Python codebases.
- **Core Logic:** Implemented in `src/modernize_attrs/__init__.py` using [LibCST](https://github.com/Instagram/LibCST) for AST transformations.
- **Entrypoint:** The CLI is exposed via `modernize_attrs.__main__:main` (see `pyproject.toml`).

## Key Workflows
- **Run Codemod:**
  - Use without install: `uvx git+https://github.com/jonathanberthias/modernize-attrs src_dir_or_file`
  - Or install locally and run: `python -m modernize_attrs <src_dir_or_file>`
- **Development Setup:**
  - Sync dependencies: `uv sync`
  - Run tests: `uv run pytest`
  - All code and tests are compatible with Python >= 3.11

## Code Patterns & Conventions
- **Transformations:**
  - Converts `@attr.s`/`@attrs.s` to `@define` (from `attrs`)
  - Moves type hints from `attr.ib(type=...)` to Python type annotations
  - Converts `attr.ib()` to `attrs.field()`
  - Removes empty `field()` calls when no arguments remain
- **Safety:**
  - Classes with `attr.ib()` lacking type hints are skipped and a warning is printed
  - Existing type annotations and other `attr.ib()` arguments (e.g., `default`, `validator`) are preserved
- **Imports:**
  - Automatically updates imports to use `from attrs import define, field`

## Testing
- **Tests are in `tests.py`** (single-file test suite)
- Uses `pytest` (see `[tool.pytest.ini_options]` in `pyproject.toml`)

## External Dependencies
- **LibCST** (>=1.5.1) for code modification
- **attrs** (>=25.1.0) for target API
- **pytest** for testing
- **ruff** for linting and formatting (dev only)

## File Structure
- `src/modernize_attrs/`: Main codemod logic
- `tests.py`: All tests
- `README.md`: Usage, behavior, and rationale
- `.github/copilot-instructions.md`: AI agent guidance (this file)

## Example Transformation
```python
import attr

@attr.s
class MyClass:
    x = attr.ib(type=int)
    y = attr.ib(type=str, default="hello")
```
Becomes:
```python
from attrs import define, field

@define
class MyClass:
    x: int
    y: str = field(default="hello")
```

## Updates

When updating the codemod, ensure these instructions remain accurate.
Also keep the README.md in sync with any changes to usage or behavior.
