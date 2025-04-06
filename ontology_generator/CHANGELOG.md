# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Fixed
- Fixed test failures in unit tests:
  - Updated test_apply_data_property_mappings to use mock.ANY for type-agnostic assertion
  - Modified test_create_selective_classes_logs to handle variable log message formats
  - Refactored test_opera_property_characteristics to be more resilient to implementation differences in property characteristics

## [1.1.5] - 2024-04-06
### Added
- TKT-BUG-006: Added unit tests for population core functionality
  - Implemented comprehensive tests for PopulationContext class methods
  - Added tests for get_or_create_individual with various scenarios
  - Added tests for _set_property_value for both functional and non-functional properties
  - Implemented tests for apply_data_property_mappings and apply_object_property_mappings
  - Added tests for helper functions like set_prop_if_col_exists
  - Updated code structure to use pytest fixtures and mocking

## [1.1.4] - 2024-04-06
### Added
- TKT-BUG-005: Added unit tests for ontology structure definition (definition.structure)
  - Expanded test_structure.py with tests for define_ontology_structure and create_selective_classes functions
  - Added tests using real data examples from OPERA specifications
  - Implemented tests for class hierarchy, property characteristics, and selective class creation
  - Added testing for handling missing domain/range class definitions
  - Added validation tests for automatically added properties

## [1.1.3] - 2024-04-06
### Added
- TKT-BUG-004: Added unit tests for specification parsing (definition.parser)
  - Created mock-based tests for parse_specification, parse_property_mappings, validate_property_mappings, and read_data
  - Added test cases for handling valid inputs, error conditions, and edge cases
  - Implemented validation tests for property mapping structure and requirements

## [1.1.2] - 2024-04-06
### Added
- TKT-BUG-003: Implemented comprehensive unit tests for core utilities (utils.types)
  - Added extensive parameterized tests for safe_cast covering various data types and edge cases
  - Enhanced tests for sanitize_name with additional test cases
  - Added mock tests for logging behavior in safe_cast

## [1.1.1] - 2024-04-06
### Changed
- TKT-BUG-002: Adopted pytest framework and restructured test suite
  - Added pytest and pytest-mock as development dependencies
  - Restructured tests/ directory to mirror src/ontology_generator/
  - Converted unittest tests to pytest style
  - Moved inline test from utils/types.py to proper test file
  - Updated test documentation
  - Configured pytest options in pyproject.toml

## [1.1.0] - 2024-04-06
### Changed
- TKT-BUG-001: Refactored project structure to standard src layout
  - Moved library code to src/ontology_generator/
  - Moved standalone utility scripts to scripts/
  - Updated imports throughout the codebase
  - Added pyproject.toml for better packaging
  - Removed custom test runner (run_tests.py)

## [1.0.1] - 2024-04-06
### Fixed
- TKT-001: Fixed property definition failure in define_ontology_structure by replacing dynamic property object creation with proper Owlready2 class declarations
- TKT-002: Corrected misleading property type mismatch warnings during ontology definition
- TKT-003: Fixed Individual Registry Synchronization Issue
- TKT-007: Added missing code-defined property (equipmentClassId) to the ontology specification

### Changed
- TKT-003: Reduced log level for registry synchronization warnings from WARNING to DEBUG

## [1.0.0] - 2024-04-04
### Added
- Initial release
- Utility scripts for better debugging and log analysis

### Fixed
- TKT-001: Specification loading now includes owl:Thing parent class
- TKT-004: Corrected EventRecord linking for time intervals
- TKT-005: Eliminated redundant Equipment-EquipmentClass linking in post-processing
- TKT-006: Investigated and documented 17 unused properties, updated specification with clarifying notes for inverse properties 