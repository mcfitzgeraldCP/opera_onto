---
name: Bug Ticket
about: Technical issue documentation for the Ontology Generator project
labels: bug
---

# Bug Ticket: [ID: TKT-BUG-XXX]

## Title
[Component] - Technical issue description

## Issue Information
**Priority**: [Critical/High/Medium/Low]
**Summary**: [Clear, concise description of the technical issue]
**Impact**: [How this affects functionality/development]
**Affected Modules**: [List the affected files/modules]

## Environment Context
_Only include if relevant to the issue:_
- Python/Package Version: [if version-specific]
- OS: [only if OS-dependent]
- Recent Changes: [any relevant recent changes]

## Technical Details
### Issue Description
[Detailed technical explanation focusing on code/data issues rather than UI/UX]

### Debug Information
```python
# Error Message/Stack Trace
[Paste relevant error output]

# Code Context
[Relevant code snippet showing the issue]

# Example:
result = ontology.define_property(name="example:property", namespace="custom")
# AttributeError: 'NoneType' object has no attribute 'iri'
```

### Tasks
- [ ] [Specific technical task to fix the issue]
- [ ] [Additional tasks as needed]
- [ ] [Verification steps]

## Testing Requirements
- [ ] Unit tests (core functionality changes)
- [ ] Integration tests (cross-component issues)
- [ ] Manual verification (simple fixes)
- [ ] Test data: [Specify test data if applicable]

## Acceptance Criteria
- [ ] [Specific verifiable outcome 1]
- [ ] [Specific verifiable outcome 2]
- [ ] [Additional criteria as needed]

## Version Impact Assessment
**Current Version:** [e.g., 1.0.1]
**Recommended Bump:** [MAJOR|MINOR|PATCH]
**Reasoning:** [Brief explanation for version choice]

**Guidelines:**
- MAJOR (x.y.z): Breaking API changes, incompatible ontology structure
- MINOR (x.Y.z): New backward-compatible features, optional ontology elements
- PATCH (x.y.Z): Bug fixes, performance improvements, non-breaking changes

**Checklist:**
- [ ] Update __init__.py version
- [ ] Update CHANGELOG.md
- [ ] Create git tag after merge

## Commit Example
```
fix(component): Brief description

Detailed explanation of the issue and fix.

Version: x.y.z
Changelog: Fixed
Ticket: TKT-BUG-XXX

- Technical details for changelog entry
```

## Related Information
- Related Issues: [Links to related issues]
- Documentation: [Links to relevant docs] 