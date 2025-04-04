# TKT-006 Implementation Plan for Core Object Properties

## Overview

This document outlines the implementation plan for addressing the 8 core object properties that were identified as unused in the TKT-006 investigation.

## Core Object Properties to Implement

The following properties require proper implementation to ensure they are set during ontology population:

1. `associatedRequest` - Links EventRecord to ProductionRequest
2. `consumedMaterial` - Links EventRecord to Material (consumed)
3. `producedMaterial` - Links EventRecord to Material (produced)
4. `duringShift` - Links EventRecord to Shift
5. `isPartOfLineEvent` - Links equipment-level EventRecord to line-level EventRecord
6. `locatedInPlant` - Links Area to Plant
7. `locatedInProcessCell` - Links ProductionLine to ProcessCell
8. `partOfArea` - Links ProcessCell to Area

## Implementation Approach

### 1. Material and Request Linking
Add code to link EventRecord to Materials and ProductionRequest in `ontology_generator/population/events.py`.

```python
# Inside process_event_related()
# After creating event_ind
if material_ind and 'EVENT_MATERIAL_ROLE' in row:
    material_role = row.get('EVENT_MATERIAL_ROLE', '').strip().upper()
    if material_role == 'PRODUCED':
        context.set_prop(event_ind, "producedMaterial", material_ind)
    elif material_role == 'CONSUMED':
        context.set_prop(event_ind, "consumedMaterial", material_ind)
    else:
        # Default to PRODUCED if role not specified but material exists
        context.set_prop(event_ind, "producedMaterial", material_ind)

# Link to production request if available
if request_ind:
    context.set_prop(event_ind, "associatedRequest", request_ind)
```

### 2. Shift Linking
Enhance the shift linking in `ontology_generator/population/events.py`:

```python
# Inside process_event_related()
# After creating event_ind and shift_ind
if shift_ind:
    context.set_prop(event_ind, "duringShift", shift_ind)
```

### 3. Asset Hierarchy Linking
Add proper hierarchy linking in `ontology_generator/population/asset.py`:

```python
# Inside process_asset_hierarchy()
# After creating plant_ind, area_ind, pcell_ind, line_ind
if area_ind and plant_ind:
    context.set_prop(area_ind, "locatedInPlant", plant_ind)

if pcell_ind and area_ind:
    context.set_prop(pcell_ind, "partOfArea", area_ind)

if line_ind and pcell_ind:
    context.set_prop(line_ind, "locatedInProcessCell", pcell_ind)
```

### 4. Event Hierarchy Linking
Enhance the event linking in `ontology_generator/population/events.py` to connect equipment-level events to line-level events:

```python
# Add function in events.py
def link_equipment_events_to_line_events(context, all_events_list, registry, logger=None):
    """
    Links equipment-level events to corresponding line-level events.
    Uses time overlap to determine relationships.
    
    Args:
        context: The PopulationContext
        all_events_list: List of (event_ind, resource_ind, resource_type) tuples
        registry: The central registry
        logger: Logger to use
        
    Returns:
        int: Count of links created
    """
    log = logger or events_logger
    log.info("Linking equipment events to line events...")
    
    # Separate line and equipment events
    line_events = []
    equipment_events = []
    
    for event_ind, resource_ind, resource_type in all_events_list:
        if resource_type == 'Line':
            line_events.append((event_ind, resource_ind))
        elif resource_type == 'Equipment':
            equipment_events.append((event_ind, resource_ind))
    
    log.info(f"Found {len(line_events)} line events and {len(equipment_events)} equipment events to link")
    
    # No linking needed if either list is empty
    if not line_events or not equipment_events:
        return 0
    
    # Get the isPartOfLineEvent property
    is_part_of_line_prop = context.get_prop("isPartOfLineEvent")
    if not is_part_of_line_prop:
        log.error("Required property 'isPartOfLineEvent' not found. Cannot link equipment events to line events.")
        return 0
    
    # Track links created
    links_created = 0
    
    # For each equipment event, find overlapping line events
    for eq_event_ind, eq_resource_ind in equipment_events:
        # Get equipment event's time interval
        eq_interval = getattr(eq_event_ind, "occursDuring", None)
        if not eq_interval:
            continue
            
        eq_start = getattr(eq_interval, "startTime", None)
        eq_end = getattr(eq_interval, "endTime", None)
        if not eq_start or not eq_end:
            continue
            
        # Get the production line this equipment belongs to
        prod_line = getattr(eq_resource_ind, "isPartOfProductionLine", None)
        if not prod_line:
            continue
            
        # Find line events for the same line with overlapping time intervals
        for line_event_ind, line_resource_ind in line_events:
            # Check if this line event is for the same line
            if line_resource_ind != prod_line:
                continue
                
            # Get line event's time interval
            line_interval = getattr(line_event_ind, "occursDuring", None)
            if not line_interval:
                continue
                
            line_start = getattr(line_interval, "startTime", None)
            line_end = getattr(line_interval, "endTime", None)
            if not line_start or not line_end:
                continue
                
            # Check for time overlap
            if (eq_start <= line_end and eq_end >= line_start):
                # Link equipment event to line event
                context.set_prop(eq_event_ind, "isPartOfLineEvent", line_event_ind)
                links_created += 1
                log.debug(f"Linked equipment event {eq_event_ind.name} to line event {line_event_ind.name}")
                # Break after finding the first match (assuming one equipment event belongs to at most one line event)
                break
    
    log.info(f"Created {links_created} equipment-to-line event links")
    return links_created
```

## Integration

Integrate these implementations in the main population process:

1. Update the `main.py` file to call `link_equipment_events_to_line_events()` during the post-processing phase.
2. Ensure all property setting uses `context.set_prop()` to properly track property usage.

## Testing

Test the implementation by:

1. Running the ontology generator with the updated code
2. Checking the property usage report to verify the properties are now being used
3. Verifying the ontology contains the expected relationships
4. Checking for any reasoner inferences that depend on these properties

## Expected Outcome

After implementation, we expect:
- All 8 core object properties to be actively used in the ontology
- Reduced number of unused properties in the property usage report
- More complete and useful ontology for downstream applications
- Proper inverse property inferences by the reasoner 