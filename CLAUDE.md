# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands
- Install development dependencies: `pip install -e ".[dev]"`
- Run all tests: `python -m pytest`
- Run a single test: `python -m pytest tests/test_file.py::test_name`
- Type checking: `mypy src/`
- Linting: `ruff check src/`
- Formatting: `black src/`
- Build package: `python -m build`

## Code Style Guidelines
- Line length: 100 characters max
- Formatting: Use black (23.0.0+)
- Type annotations: Required for all functions (mypy with strict settings)
- Imports: Use absolute imports, sorted with ruff
- Naming: Follow Python PEP8 conventions (snake_case for variables/functions)
- Error handling: Use try/except blocks with specific exception types
- Documentation: Include docstrings for public APIs
- Testing: Write unit tests for all new functionality