# TKT-006 Investigation: 17 Unused Properties

## Issue Summary
The property usage report from the ontology generator indicates that 17 out of 29 defined properties were never set on any individual, suggesting potential mapping issues or unnecessary property definitions.

## Investigation Process

1. Analyzed logs showing 17 unused properties out of 29 total properties
2. Created and ran a property analysis script to identify the unused properties by comparing:
   - Properties defined in the OPERA_ISA95_OWL_ONT_V25.csv specification
   - Properties requested by the code during population

3. Key findings from the logs:
   - 29 total properties defined in the ontology
   - Only 12 properties (41.4%) were successfully used (set on individuals)
   - 17 properties (58.6%) were never used
   - 53 undefined properties were requested, indicating potential mapping issues

## Identified Unused Properties
Based on our analysis, the following properties appear to be defined but unused:

1. **Object Properties**:
   - associatedRequest
   - consumedMaterial
   - containsProductionLine
   - duringShift
   - hasArea
   - hasAssociatedEvent
   - hasDetailedEquipmentEvent
   - hasEquipmentPart
   - hasInstance
   - hasProcessCell
   - isMaterialConsumedIn
   - isMaterialProducedIn
   - isPartOfLineEvent
   - locatedInPlant
   - locatedInProcessCell
   - partOfArea
   - resourceInvolvedIn

2. **Data Properties**:
   (There were no unused data properties identified)

## Root Cause Analysis

The problem appears to be related to two primary issues:

1. **Object property pairs**: Many of the unused properties are inverse properties for properties that *are* actually used. For example, while `involvesResource` is used, its inverse property `resourceInvolvedIn` is not. This suggests that the population code might be setting only one direction of the relationship, and the reasoner is expected to infer the inverse relationships.

2. **Mapping issues**: The log shows 53 undefined properties were requested, suggesting there's a mismatch between the property names defined in the specification and the property names requested in the code.

## Categorization of Unused Properties

### Inverse Object Properties (Expected Unused)
These properties are inverse properties that are expected to be inferred by the reasoner:

1. resourceInvolvedIn (inverse of involvesResource)
2. hasEquipmentPart (inverse of isPartOfProductionLine)
3. hasInstance (inverse of memberOfClass)
4. hasArea (inverse of locatedInPlant)
5. hasProcessCell (inverse of partOfArea)
6. containsProductionLine (inverse of locatedInProcessCell)
7. hasAssociatedEvent (inverse of associatedRequest)
8. hasDetailedEquipmentEvent (inverse of isPartOfLineEvent)
9. isMaterialProducedIn (inverse of producedMaterial)
10. isMaterialConsumedIn (inverse of consumedMaterial)

### Unused Core Object Properties (Require Implementation)
These properties appear to be core relationships that should be implemented:

1. associatedRequest
2. consumedMaterial
3. producedMaterial
4. duringShift
5. isPartOfLineEvent
6. locatedInPlant
7. locatedInProcessCell
8. partOfArea

## Missing Property Mappings
The logs indicate 53 undefined properties were requested. This suggests a mismatch between property names in the specification and those used in the code.

## Recommended Actions

1. **Acknowledge inverse properties**: Document that the 10 inverse properties are intentionally not directly set but inferred by the reasoner.

2. **Implement missing core properties**: Add implementation for the 8 core object properties that are currently unused.

3. **Fix property mappings**: Address the mismatch between property names in the specification and those used in the code.

4. **Update configuration**: Ensure that property names in the OPERA_ISA95_OWL_ONT_V25.csv specification match those used in the code.

## Implementation Strategy

1. For inverse properties: Add comments in the specification to indicate these are expected to be inferred.
2. For core unused properties: Add code to properly populate these relationships.
3. For property mappings: Ensure property names in specification match those in the code.

## TKT-007 Resolution: Code-Defined Properties Added to Specification

As part of TKT-007, we identified properties that were programmatically defined in the code but were missing from the specification CSV. Our investigation showed that most of the properties used in the code were already defined in the specification, but with "N/A" in the Raw Data Column Name field and the "Programmatic" field set to "True".

However, we identified and added the following missing property to the specification:

1. `equipmentClassId` (EquipmentClass DataProperty) - This property is used to uniquely identify equipment class individuals and is set programmatically during population.

The following properties were already correctly defined in the specification with programmatic indicators:
- sequencePosition
- isImmediatelyUpstreamOf
- isImmediatelyDownstreamOf
- isPartOfProductionLine
- memberOfClass
- isParallelWith 

With this update, the specification now accurately reflects all the properties used in the code, ensuring it serves as the single source of truth for the ontology structure.

## Impact Assessment

Fixing these issues will:
1. Improve the completeness of the ontology
2. Increase property usage from 41.4% to a much higher percentage
3. Ensure that all essential relationships are properly represented
4. Make the ontology more useful for downstream applications
5. Keep the specification synchronized with the code implementation

## Timeline
Low priority task that can be completed after fixing TKT-001 and TKT-004, as indicated in the ticket description. 