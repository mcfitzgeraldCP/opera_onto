# Ontology Generator

A modular Python application for generating OWL ontologies from CSV specifications and data.

## Project Structure

```
ontology_generator/
├── __init__.py
├── config.py                 # Configuration constants and settings
├── main.py                   # Main script entry point
├── definition/
│   ├── __init__.py
│   ├── parser.py             # Specification parsing
│   └── structure.py          # Ontology structure definition
├── population/
│   ├── __init__.py
│   ├── asset.py              # Asset hierarchy processing
│   ├── core.py               # Core population functionality
│   ├── equipment.py          # Equipment processing
│   ├── events.py             # Event record processing
│   ├── linking.py            # Event linking functionality
│   └── sequence.py           # Sequence relationship setup
├── analysis/
│   ├── __init__.py
│   ├── population.py         # Population analysis
│   └── reasoning.py          # Reasoning analysis and reporting
└── utils/
    ├── __init__.py
    ├── logging.py            # Logging utilities
    └── types.py              # Type conversion utilities
```

## Documentation

- [Migration Guide](migration_guide.md): Information for migrating from previous versions
- [Event Linking Guide](docs/event_linking_guide.md): Detailed information about event linking functionality and parameters

## Requirements

- Python 3.6+
- owlready2
- dateutil

## Usage

```bash
python -m ontology_generator.main spec_file data_file output_file [options]
```

### Command-line Arguments

- `spec_file`: Path to the ontology specification CSV file
- `data_file`: Path to the operational data CSV file
- `output_file`: Path to save the generated OWL ontology file

### Options

- `--iri`: Base IRI for the ontology (default: "http://example.com/manufacturing_ontology.owl")
- `--format`: Format for saving the ontology (default: "rdfxml", choices: "rdfxml", "ntriples", "nquads", "owlxml")
- `--reasoner`: Run the reasoner after population
- `--worlddb`: Path to use/create a persistent SQLite world database
- `--max-report-entities`: Maximum number of entities to show per category in the reasoner report (default: 10)
- `--full-report`: Show full details in the reasoner report
- `--no-analyze-population`: Skip analysis and reporting of ontology population
- `--strict-adherence`: Only create classes explicitly defined in the specification
- `--skip-classes`: List of class names to skip during ontology creation
- `--optimize`: Generate detailed optimization recommendations
- `--event-buffer`: Time buffer in minutes for event linking (default: 5)
- `--test-mappings`: Test the property mapping functionality only
- `-v, --verbose`: Enable verbose (DEBUG level) logging
- `-q, --quiet`: Suppress INFO level logging

## Module Overview

### Definition Module

- `parser.py`: Functions for parsing the ontology specification CSV file
- `structure.py`: Functions for defining the ontology structure (classes and properties)

### Population Module

- `core.py`: Core population functionality including the `PopulationContext` class
- `asset.py`: Functions for processing asset hierarchy data
- `equipment.py`: Functions for processing equipment data
- `events.py`: Functions for processing event-related data
- `linking.py`: Functions for linking equipment events to line events
- `sequence.py`: Functions for setting up equipment sequence relationships

### Analysis Module

- `population.py`: Functions for analyzing the ontology population
- `reasoning.py`: Functions for generating reasoning reports

### Utils Module

- `logging.py`: Utilities for setting up and configuring logging
- `types.py`: Utilities for safe type conversion

## Example

```bash
python -m ontology_generator.main spec.csv data.csv output.owl --reasoner --optimize -v
```

This will:
1. Parse the specification from `spec.csv`
2. Load data from `data.csv`
3. Generate an ontology based on the specification
4. Populate the ontology with individuals from the data
5. Run the reasoner on the populated ontology
6. Generate optimization recommendations
7. Save the result to `output.owl`
8. Provide verbose logging output

## Testing

To test the property mapping functionality without generating an ontology:

```bash
python -m ontology_generator.main spec.csv data.csv output.owl --test-mappings
```

## Event Linking

When working with sample datasets or data with timing gaps, you may need to adjust the event buffer to improve linking success:

```bash
python -m ontology_generator.main spec.csv data.csv output.owl --event-buffer 15
```

This increases the time window for matching equipment events to line events from the default 5 minutes to 15 minutes. See the [Event Linking Guide](docs/event_linking_guide.md) for detailed information.