# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.4] - 2024-05-06
### Added
- TKT-BUG-005: Added unit tests for ontology structure definition (definition.structure)
  - Comprehensive test coverage for define_ontology_structure and create_selective_classes functions
  - Tests for class hierarchies, property characteristics, domains, ranges, and inverse properties
  - Tests for handling missing definitions and special properties
  - Tests for selective class creation with different options 