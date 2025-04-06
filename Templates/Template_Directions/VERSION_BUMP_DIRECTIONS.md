# Version Bump Directions

## Overview
This directive guides the process of version bumping and changelog updates for the Ontology Generator project. Add this section to your bug fix tickets to assess and document version changes.

## Version Assessment Template
```markdown
### Version Impact Assessment
**Current Version:** [e.g., 1.0.1]
**Recommended Bump:** [MAJOR|MINOR|PATCH]
**Reasoning:** [Brief explanation of why this level was chosen]

#### Checklist
- [ ] Update __init__.py version
- [ ] Update CHANGELOG.md
- [ ] Create git tag after merge
```

## Version Bump Guidelines

### MAJOR Version Bump (X.y.z)
Required when:
- Breaking changes to the API or data structure
- Changes that require users to modify their code
- Incompatible changes to ontology structure
- Major refactoring that affects external interfaces

### MINOR Version Bump (x.Y.z)
Required when:
- New features added in a backward-compatible manner
- New optional ontology elements introduced
- Substantial new functionality that doesn't break existing features
- Deprecation of existing functionality (but not removal)

### PATCH Version Bump (x.y.Z)
Required when:
- Bug fixes that don't change the API
- Performance improvements
- Documentation updates
- Minor code refactoring
- Non-breaking changes to logging or error messages

## Commit Message Format
```
type(scope): Brief description of the change

[Optional body with detailed explanation]

Version: x.y.z
Changelog: Added|Changed|Deprecated|Removed|Fixed|Security
Ticket: TKT-XXX

- Detailed changelog entry that will be added to CHANGELOG.md
- Any additional notes or related changes
```

### Commit Type Keywords
- fix: Bug fixes (PATCH)
- feat: New features (MINOR)
- BREAKING CHANGE: Breaking changes (MAJOR)
- chore: Maintenance tasks
- docs: Documentation updates
- style: Code style changes
- refactor: Code refactoring
- perf: Performance improvements
- test: Test updates

## Example
```markdown
### Version Impact Assessment
Current Version: 1.0.1
Recommended Bump: PATCH
Reasoning: Bug fix for property definition that doesn't affect API or data structure

#### Checklist
- [ ] Update __init__.py version to 1.0.2
- [ ] Update CHANGELOG.md
- [ ] Create git tag v1.0.2 after merge

Commit Message:
fix(ontology): Correct property definition failure in define_ontology_structure

Fixed dynamic property object creation by replacing with proper Owlready2
class declarations. Resolves AttributeError where property objects had no
'iri' attribute.

Version: 1.0.2
Changelog: Fixed
Ticket: TKT-001

- Fixed property definition failure in define_ontology_structure by replacing
  dynamic property object creation with proper Owlready2 class declarations
```

## Important Notes
1. Always update both `__init__.py` and `CHANGELOG.md` together
2. Keep changes atomic and well-documented
3. If in doubt about version bump level, discuss with team lead
4. Tag releases in git after merge to main branch
5. Test thoroughly before bumping MAJOR version 