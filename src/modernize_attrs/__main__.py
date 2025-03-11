import sys
from pathlib import Path
from typing import Sequence

from libcst.codemod import CodemodContext, parallel_exec_transform_with_prettyprint

from modernize_attrs import ModernizeAttrsCodemod


def main(paths: Sequence[str] | None = None) -> int:
    """
    Main entry point for the modernize-attrs command-line tool.
    
    Args:
        paths: Optional sequence of paths to process. If None, uses sys.argv[1:]
    
    Returns:
        0 on success, non-zero on error
    """
    if paths is None:
        paths = sys.argv[1:]

    if not paths:
        print("Error: No paths provided")
        print("Usage: modernize-attrs <path(s)>")
        return 1

    # Convert all paths to absolute Path objects and validate they exist
    path_objects = []
    for path in paths:
        p = Path(path).resolve()
        if not p.exists():
            print(f"Error: Path does not exist: {path}")
            return 1
        path_objects.append(p)

    # Collect all Python files from the provided paths
    files_to_process = []
    for path in path_objects:
        if path.is_file() and path.suffix == '.py':
            files_to_process.append(str(path))
        elif path.is_dir():
            files_to_process.extend(str(p) for p in path.rglob('*.py') if p.is_file())

    if not files_to_process:
        print("No Python files found to process")
        return 1

    # Run the codemod
    result = parallel_exec_transform_with_prettyprint(
        ModernizeAttrsCodemod(CodemodContext()),
        files_to_process,
    )

    # Return 0 if all files were processed successfully
    return 0 if result.successes == len(files_to_process) else 1


if __name__ == "__main__":
    sys.exit(main()) 