# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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