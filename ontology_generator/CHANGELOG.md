# Changelog

## [Unreleased]

### Fixed
- TKT-001: Fixed property definition failure in define_ontology_structure by replacing dynamic property object creation with proper Owlready2 class declarations. This resolves the AttributeError where property objects had no 'iri' attribute and fixes cascading failures in population and event linking.
- TKT-002: Corrected misleading property type mismatch warnings during ontology definition. Fixed the validation check to properly verify property types using instanceof instead of comparing class names.
- TKT-003: Fixed Individual Registry Synchronization Issue that caused warnings when individuals were found in the ontology but not in the script's registry. Improved the synchronization mechanism in get_or_create_individual to properly handle individuals created outside the registry. Added tests for the sanitize_name function and registry synchronization. 
- TKT-007: Added missing code-defined property (equipmentClassId) to the ontology specification. Ensured all programmatically defined properties are properly documented in the OPERA_ISA95_OWL_ONT_V25.csv specification file, maintaining it as the single source of truth.

### Changed
- TKT-003: Reduced log level for registry synchronization warnings from WARNING to DEBUG to decrease log noise, as the recovery mechanism properly handles these situations.

## 2023-04-04
- Added utility scripts for better debugging and log analysis
- Fixed TKT-001: Specification loading now includes owl:Thing parent class
- Fixed TKT-004: Corrected EventRecord linking for time intervals
- Fixed TKT-005: Eliminated redundant Equipment-EquipmentClass linking in post-processing
- Fixed TKT-006: Investigated and documented 17 unused properties, updated specification with clarifying notes for inverse properties, and created implementation plan for adding support for missing core properties 