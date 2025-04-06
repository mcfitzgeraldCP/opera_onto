# Bug Ticket Directions

This document provides guidance on documenting bugs during rapid development of the Ontology Generator project. These directions are optimized for developer-centric issues rather than end-user bug reports.

## Core Principles
1. Focus on code and data issues rather than UI/UX problems
2. Prioritize technical details over detailed reproduction steps
3. Include relevant code snippets and error messages
4. Reference version control guidelines for proper versioning
5. Keep documentation lean but informative

## Section Guide

### Title & Description
- Use format: `[Component] - Technical issue description`
- Example: `[PropertyGenerator] - Null IRI in custom namespace definition`
- Include impact on development/functionality
- Note any blocking issues or dependencies

### Environment Context
Essential information only:
- Python/package versions if version-specific
- OS only if OS-dependent
- Special environment setup if relevant
- Recent changes that might affect the bug

### Reproduction
Keep it focused on the technical scenario:
```markdown
## Steps to Reproduce
- Input: [data file/code snippet/test case]
- Action: [function call/operation performed]
- Output: [error/unexpected result]
```

### Debug Information
Prioritize including:
- Stack traces
- Error messages
- Relevant log entries
- Code snippets showing the issue
- Input data samples if needed

Example:
```python
# Code that triggers the issue
result = ontology.define_property(
    name="example:property",
    namespace="custom"
)

# Error received
AttributeError: 'NoneType' object has no attribute 'iri'
```

### Version Impact Assessment
Follow VERSION_BUMP_DIRECTIONS.md guidelines. Quick reference:
- MAJOR: Breaking API changes
- MINOR: New features, backward compatible
- PATCH: Bug fixes, no API changes

Example assessment:
```markdown
Current Version: 1.0.1
Recommended: PATCH
Reasoning: Internal bug fix, no API changes
```

### Testing Requirements
Focus on necessary validation:
- Unit tests: Only for core functionality changes
- Integration tests: For cross-component issues
- Manual verification: For simple fixes or UI/logging issues

Example:
```markdown
## Testing Requirements
- [ ] Manual verification (log output fix)
- [ ] Test data: sample_ontology.owl
```

### Solution Notes
Brief technical notes about:
- Root cause if known
- Proposed fix approach
- Related code areas
- Potential side effects

## Example Bug Report (Development Context)

```markdown
# Bug Report

## Title
[OntologyLoader] - Failed to parse custom datatype definitions

## Description
**Summary**: Datatype parser throws TypeError when processing non-standard XML datatypes
**Impact**: Blocks custom datatype support in development branch
**Reproducibility**: 100% with test data

## Debug Information
**Error Message**: 
```
TypeError: unsupported datatype: 'custom:integer'
Stack trace: [...]
```

**Code Context**: 
```python
datatype = ontology.define_datatype('custom:integer')
# TypeError occurs in datatype_parser.py:123
```

## Version Impact Assessment
**Current Version:** 1.0.1
**Recommended Bump:** PATCH
**Reasoning:** Internal parser fix, no API changes

## Testing Requirements
- [ ] Manual verification with test data
- [ ] Test file: test_datatypes.owl

## Related Information
- Similar issue fixed in PR #45
- Affects datatype_parser.py and xml_handler.py
```

## Additional Notes
1. For rapid development, focus on technical details over user-facing documentation
2. Include minimal but sufficient information to understand and fix the issue
3. Reference related code/PRs when possible
4. Keep version control practices consistent using VERSION_BUMP_DIRECTIONS.md 