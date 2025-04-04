# Ontology Generator Tests

This directory contains tests for various components of the ontology generator.

## Running Tests

To run all tests, execute the run_tests.py script from the project root:

```bash
python -m ontology_generator.run_tests
```

## Test Descriptions

### Registry Synchronization Test (TKT-003)

This test verifies the fix for TKT-003 (Individual Registry Synchronization Issue) by:

1. Creating an individual directly in the ontology (bypassing the registry)
2. Attempting to create the same individual via get_or_create_individual
3. Verifying the registry is properly synchronized and no duplicate is created

Run this test individually:

```bash
python -m ontology_generator.tests.test_registry_sync
```

### Sanitize Name Tests

These tests verify the behavior of the sanitize_name function in utils.types, which is used to generate consistent individual names and registry keys.

Run these tests individually:

```bash
python -m ontology_generator.utils.types
``` 