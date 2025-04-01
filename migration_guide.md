# Migration Guide

This guide explains the changes between the original monolithic script (`reference_original.py` formerly `create_ontology_V7.py`) and the refactored modular version.

## Overview of Changes

The original script was a ~3000-line single file. It has been reorganized into a modular package structure without changing the core functionality. The changes were focused on:

1. Improving code organization
2. Reducing coupling between components
3. Improving maintainability and readability
4. Making the code more extensible

## Directory Structure

The code is now organized into logical modules:

```
ontology_generator/
├── __init__.py
├── config.py                 # Configuration constants and settings
├── main.py                   # Main script entry point
├── definition/               # Ontology definition (TBox)
├── population/               # Ontology population (ABox)
├── analysis/                 # Analysis and reporting
└── utils/                    # Utilities
```

## Function Mapping

Here's a mapping of key functions from the original script to the new modules:

| Original Function | New Location |
|-------------------|-------------|
| `parse_specification()` | `ontology_generator.definition.parser.parse_specification()` |
| `define_ontology_structure()` | `ontology_generator.definition.structure.define_ontology_structure()` |
| `create_selective_classes()` | `ontology_generator.definition.structure.create_selective_classes()` |
| `process_asset_hierarchy()` | `ontology_generator.population.asset.process_asset_hierarchy()` |
| `process_equipment()` | `ontology_generator.population.equipment.process_equipment()` |
| `process_event_record()` | `ontology_generator.population.events.process_event_record()` |
| `setup_equipment_sequence_relationships()` | `ontology_generator.population.sequence.setup_equipment_sequence_relationships()` |
| `link_equipment_events_to_line_events()` | `ontology_generator.population.linking.link_equipment_events_to_line_events()` |
| `analyze_ontology_population()` | `ontology_generator.analysis.population.analyze_ontology_population()` |
| `generate_reasoning_report()` | `ontology_generator.analysis.reasoning.generate_reasoning_report()` |

## Logging Changes

Logging is now more consistently handled across modules:

- `main_logger` for the main script
- `logger` for definition module
- `pop_logger` for population module
- `link_logger` for event linking
- `analysis_logger` for analysis module

All loggers are configured through the `ontology_generator.utils.logging.configure_logging()` function.

## Configuration Changes

Constants and configuration settings have been moved to `ontology_generator.config`. This includes:

- Default IRI
- Language mappings
- Equipment sequence definitions
- XSD type mappings

## Command-line Interface

The command-line interface remains largely unchanged, with all the same options available. The main difference is how to invoke the script:

Old:
```bash
python create_ontology_V7.py spec.csv data.csv output.owl
```

New:
```bash
python -m ontology_generator.main spec.csv data.csv output.owl
```

Or if installed via pip:
```bash
ontology-generator spec.csv data.csv output.owl
```

## Key Class Changes

A new `PopulationContext` class has been introduced in `ontology_generator.population.core` to handle the context for population operations. This replaces scattered parameters that were previously passed around.

## How To Verify Correctness

To verify that the refactored code behaves the same as the original:

1. Run the original script with your data
2. Run the new script with the same data
3. Compare the output ontology files (they should be identical or at least logically equivalent)

## Troubleshooting

If you encounter issues with the refactored code:

1. Check for module import errors (you might need to install the package or adjust PYTHONPATH)
2. Verify that all required packages are installed (`owlready2`, `python-dateutil`)
3. Check the logs for specific error messages

## Extending the Code

The modular structure makes it easier to extend the code:

- Add new parser formats in `definition/parser.py`
- Add support for new population patterns in the `population/` package
- Add new analysis methods in the `analysis/` package

## Future Improvements

Potential areas for further improvement:

1. Adding unit tests for each module
2. Creating a formal API for extending the code
3. Implementing class-based design with proper inheritance
4. Adding support for different ontology formats and structures 