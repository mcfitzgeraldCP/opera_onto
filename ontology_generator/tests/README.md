# Ontology Generator Tests

This directory contains tests for the ontology generator library.

## Running Tests

To run all tests, execute pytest from the project root:

```bash
python -m pytest
```

You can also run specific test files or directories:

```bash
# Run a specific test file
python -m pytest tests/utils/test_types.py

# Run tests in a specific directory
python -m pytest tests/definition/

# Run tests with a specific name pattern
python -m pytest -k "test_sanitize"
```

## Test Structure

The test directory structure mirrors the source code structure:

```
tests/
├── definition/ - Tests for ontology definition components
├── population/ - Tests for ontology population components
├── utils/ - Tests for utility functions
└── analysis/ - Tests for ontology analysis components
```

## Development

### Adding Tests

When adding new tests:

1. Place tests in the appropriate directory matching the source code structure
2. Name test files with a `test_` prefix
3. Name test functions with a `test_` prefix
4. Use pytest fixtures for common setup/teardown operations

### Test Dependencies

The test suite uses pytest and related packages, which are listed in the project's dev dependencies.
Install them with:

```bash
pip install -e ".[dev]"
``` 