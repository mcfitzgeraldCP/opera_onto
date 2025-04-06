# Ontology Generator

A modular Python application for generating OWL ontologies from CSV specifications and data.

## Project Structure

- `src/ontology_generator/`: Core library modules
  - `analysis/`: Ontology analysis tools
  - `definition/`: Ontology structure definition
  - `population/`: Ontology population from data
  - `utils/`: Utility functions and helpers
  - `config.py`: Configuration settings
  - `main.py`: Main entry point
- `scripts/`: Standalone utility scripts
  - `finds_unused_properties.py`: Tool to find unused properties
  - `ontology_analyzer.py`: Tool to analyze existing ontologies
- `tests/`: Test modules for the library

## Installation

From the project directory:

```bash
pip install -e .
```

## Usage

```bash
# Generate an ontology from specification and data
ontology-generator --spec path/to/spec.csv --data path/to/data.csv --output path/to/output.owl

# Analyze an existing ontology
ontology-analyzer path/to/ontology.owl

# Find unused properties
finds-unused-properties path/to/spec.csv "prop1,prop2,prop3"
```

## Development

See the [CHANGELOG.md](CHANGELOG.md) for a history of changes.

Current version: 1.1.0 