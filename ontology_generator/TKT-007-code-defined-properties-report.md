# TKT-007 Resolution: Code-Defined Properties in Specification

## Issue Summary
The ontology generator codebase programmatically defined and used certain properties that were not present in the input specification CSV (OPERA_ISA95_OWL_ONT_V25.csv). To maintain the specification as the single source of truth, these properties needed to be identified and added to the specification CSV.

## Investigation Process

1. Reviewed the codebase, particularly focusing on:
   - `ontology_generator/definition/structure.py`
   - `ontology_generator/population/sequence.py`
   - `ontology_generator/population/equipment.py`

2. Identified properties that are created and used programmatically but might not be defined in the CSV

3. Compared the identified properties with those already defined in the specification

## Key Findings

1. Most programmatically defined properties were already present in the CSV specification with the following indicators:
   - "N/A" in the Raw Data Column Name field (indicating no direct data source)
   - "True" in the Programmatic field

2. The following properties were already correctly defined in the specification:
   - `sequencePosition` (Equipment DataProperty)
   - `isImmediatelyUpstreamOf` (Equipment ObjectProperty)
   - `isImmediatelyDownstreamOf` (Equipment ObjectProperty)
   - `isPartOfProductionLine` (Equipment ObjectProperty)
   - `memberOfClass` (Equipment ObjectProperty)
   - `isParallelWith` (Equipment ObjectProperty)

3. One property was identified as missing from the specification:
   - `equipmentClassId` (EquipmentClass DataProperty)

## Implementation Actions

1. Added the missing `equipmentClassId` property to the OPERA_ISA95_OWL_ONT_V25.csv with the following details:
   - Logical Group: Equipment Class
   - Raw Data Column Name: N/A
   - Proposed OWL Entity: EquipmentClass
   - Proposed OWL Property: equipmentClassId
   - OWL Property Type: DatatypeProperty
   - Target/Range: xsd:string
   - OWL Property Characteristics: Functional
   - Domain: EquipmentClass
   - ISA-95 Concept: EquipmentClass ID
   - Parent Class: owl:Thing
   - Target Link Context: EquipmentClass
   - Notes: Identifier for the equipment class. Used to uniquely identify equipment class individuals. Set programmatically during population.
   - Programmatic: True

2. Updated `TKT-006-unused-properties-report.md` to reflect the changes made for TKT-007

## Impact Assessment

1. **Specification Completeness**: The specification now accurately reflects all properties used in the code, ensuring it serves as the single source of truth.

2. **Code-Specification Alignment**: Addressed the gap between what's defined in the specification and what's used in the code.

3. **Maintainability Improvement**: Future developers will have a more accurate understanding of the ontology structure from the specification alone.

4. **TKT-006 Support**: This work complements TKT-006 by ensuring that when unused properties are analyzed, the baseline specification is complete and accurate.

## Verification

The `equipmentClassId` property is used extensively in the codebase, particularly in:
- `ontology_generator/population/equipment.py` - Where it's set during equipment class creation
- `ontology_generator/population/sequence.py` - Where it's used to identify equipment classes

With this property now properly documented in the specification, the ontology model is more transparent and self-documenting.

## Conclusion

This task successfully addressed the missing property in the specification, ensuring that the CSV specification now accurately reflects all properties used in the code. This makes the specification a more reliable reference for the ontology structure and improves the maintainability of the codebase. 