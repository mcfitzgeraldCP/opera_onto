# Changelog

## [Unreleased]

### Fixed
- TKT-003: Fixed Individual Registry Synchronization Issue that caused warnings when individuals were found in the ontology but not in the script's registry. Improved the synchronization mechanism in get_or_create_individual to properly handle individuals created outside the registry. Added tests for the sanitize_name function and registry synchronization. 
- TKT-007: Added missing code-defined property (equipmentClassId) to the ontology specification. Ensured all programmatically defined properties are properly documented in the OPERA_ISA95_OWL_ONT_V25.csv specification file, maintaining it as the single source of truth.

## 2023-04-04
- Added utility scripts for better debugging and log analysis
- Fixed TKT-001: Specification loading now includes owl:Thing parent class
- Fixed TKT-004: Corrected EventRecord linking for time intervals
- Fixed TKT-005: Eliminated redundant Equipment-EquipmentClass linking in post-processing
- Fixed TKT-006: Investigated and documented 17 unused properties, updated specification with clarifying notes for inverse properties, and created implementation plan for adding support for missing core properties 