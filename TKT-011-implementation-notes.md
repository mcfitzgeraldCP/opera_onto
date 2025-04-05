# TKT-011: Unexpected Individual Created for ProductionLineOrEquipment Class

## Problem Description

The ontology population analysis report showed 1 individual for the `ProductionLineOrEquipment` class. This class is defined in the specification as an abstract superclass or union class for the range of the `involvesResource` property, and it is not expected to have direct instances. The `involvesResource` property links an `EventRecord` to either a `ProductionLine` or an `Equipment` resource, both of which are subclasses of `ProductionLineOrEquipment`.

## Root Cause Analysis

After investigating the codebase, we determined that:

1. The `ProductionLineOrEquipment` class is correctly defined in the specification (OPERA_ISA95_OWL_ONT_V26.csv) as a structural class for type purposes.
2. The `involvesResource` property is also correctly defined with `ProductionLineOrEquipment` as its range.
3. However, there was no explicit check to prevent the `get_or_create_individual` function from creating instances of the `ProductionLineOrEquipment` class directly.
4. The ontology generator was inadvertently creating an instance of this class somewhere in the event processing pipeline, likely in the context of setting the `involvesResource` property.

## Solution Implemented

The following changes were made to fix this issue:

1. Added a check in the `get_or_create_individual` function in `ontology_generator/population/core.py` to prevent direct creation of `ProductionLineOrEquipment` individuals:
```python
# TKT-011: Check if this is trying to create a ProductionLineOrEquipment individual,
# which should only be a structural class and not have direct instances
if onto_class and onto_class.name == "ProductionLineOrEquipment":
    pop_logger.warning(f"Attempt to create individual of abstract class ProductionLineOrEquipment with base '{individual_name_base}'. This class should not have direct instances.")
    return None
```

2. Enhanced the event processing code in `ontology_generator/population/events.py` to add documentation and additional checks to emphasize that the `involvesResource` property should only link to concrete subclasses (either `Equipment` or `ProductionLine`), never directly to instances of the abstract `ProductionLineOrEquipment` class.

## Expected Results

After implementing these changes:

1. No individuals should be created for the `ProductionLineOrEquipment` class.
2. The ontology population report should not list any individuals for this class.
3. Events will still be correctly linked to either `Equipment` or `ProductionLine` resources via the `involvesResource` property.
4. Any attempt to create a `ProductionLineOrEquipment` individual will be logged as a warning and prevented.

This change ensures that the ontology correctly follows the principle that abstract/union classes should not have direct instances. 