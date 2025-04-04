"""
Sequence relationship module for the ontology generator.

This module provides functions for setting up equipment sequence relationships.
"""
from typing import Dict, Any, List, Optional, Tuple

from owlready2 import Thing, Ontology, ThingClass, PropertyClass

from ontology_generator.utils.logging import pop_logger
from ontology_generator.population.core import PopulationContext, _set_property_value
from ontology_generator.config import DEFAULT_EQUIPMENT_SEQUENCE, LINE_SPECIFIC_EQUIPMENT_SEQUENCE

def _safe_sort_by_position(items, default_position=999999):
    """
    Safely sorts items by position value, handling None values gracefully.
    
    Args:
        items: Dictionary items (key, value) where value might be None
        default_position: Default value to use for None positions
        
    Returns:
        Sorted list of (key, value) tuples
    """
    def get_safe_position(item):
        key, position = item
        if position is None:
            pop_logger.warning(f"Found None position for {key}, using default position {default_position} for sorting")
            return default_position
        return position
        
    return sorted(items, key=get_safe_position)

def setup_equipment_instance_relationships(onto: Ontology,
                                          defined_classes: Dict[str, ThingClass],
                                          defined_properties: Dict[str, PropertyClass],
                                          property_is_functional: Dict[str, bool],
                                          equipment_class_positions: Dict[str, int]):
    """
    Establish upstream/downstream relationships between equipment *instances* within the same production line.
    
    The approach:
    1. Group equipment instances by production line
    2. For each line:
        a. Determine equipment class sequence positions using line-specific or default configuration
        b. Assign sequencePosition to each Equipment instance based on its class's position
        c. Sort instances on the line by sequencePosition and then by equipmentId (for same position)
        d. Link sorted instances with isImmediatelyUpstreamOf/isImmediatelyDownstreamOf relationships
    
    Args:
        onto: The ontology
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        property_is_functional: Dictionary indicating whether properties are functional
        equipment_class_positions: Dictionary mapping equipment class names to sequence positions
    """
    pop_logger.info("Setting up INSTANCE-LEVEL equipment relationships within production lines...")
    
    # Log about equipment class positions for diagnostics
    if not equipment_class_positions:
        pop_logger.warning("Equipment class positions dictionary is empty. We'll still process equipment instances that have sequence positions set directly.")
    else:
        pop_logger.info(f"Using {len(equipment_class_positions)} equipment class positions for processing.")
        for class_name, position in sorted(equipment_class_positions.items(), key=lambda x: x[1]):
            pop_logger.debug(f"  • Class '{class_name}' has position {position}")

    # Get context for properties/classes
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)

    # Get the required classes and properties
    cls_Equipment = context.get_class("Equipment")
    cls_ProductionLine = context.get_class("ProductionLine")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    
    # Get instance-level properties
    prop_isPartOfProductionLine = context.get_prop("isPartOfProductionLine")
    prop_memberOfClass = context.get_prop("memberOfClass")
    prop_equipmentClassId = context.get_prop("equipmentClassId")
    prop_equipmentId = context.get_prop("equipmentId")
    prop_sequencePosition = context.get_prop("sequencePosition")
    prop_isImmediatelyUpstreamOf = context.get_prop("isImmediatelyUpstreamOf")
    prop_isImmediatelyDownstreamOf = context.get_prop("isImmediatelyDownstreamOf")
    
    # TKT-007: Get isParallelWith property
    prop_isParallelWith = context.get_prop("isParallelWith")

    # Check essentials
    required_components = [
        cls_Equipment, cls_ProductionLine, cls_EquipmentClass,
        prop_isPartOfProductionLine, prop_memberOfClass, prop_equipmentClassId,
        prop_equipmentId, prop_sequencePosition, prop_isImmediatelyUpstreamOf
    ]
    
    missing_components = [name for i, name in enumerate([
        "Equipment", "ProductionLine", "EquipmentClass",
        "isPartOfProductionLine", "memberOfClass", "equipmentClassId",
        "equipmentId", "sequencePosition", "isImmediatelyUpstreamOf"
    ]) if not required_components[i]]
    
    if missing_components:
        pop_logger.error(f"Missing required components for equipment sequencing: {', '.join(missing_components)}")
        return
    
    # TKT-007: Check if isParallelWith property exists
    if not prop_isParallelWith:
        pop_logger.warning("'isParallelWith' property not found. Parallel equipment relationships will not be established.")

    if not prop_isImmediatelyDownstreamOf:
        pop_logger.warning("'isImmediatelyDownstreamOf' inverse property not found. Only forward instance relationships will be set.")

    # Group equipment instances by line
    pop_logger.info("Grouping equipment instances by production line...")
    line_equipment_map: Dict[Thing, List[Thing]] = {}  # {line_individual: [equipment_instances]}
    
    # Track lines with equipment but no sequence
    lines_without_sequence: List[str] = []

    # Count totals for diagnostic tracking
    total_equipment_processed = 0
    total_equipment_with_class = 0
    total_equipment_with_line = 0
    total_equipment_with_sequence_position = 0  # Track how many have sequencePosition set
    
    # Step 1: Group all Equipment instances by ProductionLine
    for equipment_inst in onto.search(type=cls_Equipment):
        total_equipment_processed += 1
        
        # Get the line(s) this equipment belongs to
        equipment_lines = getattr(equipment_inst, prop_isPartOfProductionLine.python_name, [])
        if not equipment_lines:
            pop_logger.debug(f"Equipment {equipment_inst.name} is not linked to any ProductionLine. Skipping.")
            continue
        
        total_equipment_with_line += 1
        
        # Get the EquipmentClass this equipment belongs to
        equipment_class_ind = getattr(equipment_inst, prop_memberOfClass.python_name, None)
        
        # More detailed logging when missing EquipmentClass link
        if not equipment_class_ind:
            eq_id = getattr(equipment_inst, prop_equipmentId.python_name, equipment_inst.name)
            pop_logger.warning(f"Equipment {eq_id} has no memberOfClass relationship. Skipping for sequence setup.")
            continue
        
        if not isinstance(equipment_class_ind, cls_EquipmentClass):
            eq_id = getattr(equipment_inst, prop_equipmentId.python_name, equipment_inst.name)
            pop_logger.warning(f"Equipment {eq_id} linked to non-EquipmentClass '{equipment_class_ind}'. Skipping for sequence setup.")
            continue
        
        total_equipment_with_class += 1
        
        # Add equipment to each of its production lines
        for line in equipment_lines:
            if not isinstance(line, cls_ProductionLine):
                pop_logger.warning(f"Equipment {equipment_inst.name} linked to non-ProductionLine '{line}'. Skipping this link.")
                continue
            
            if line not in line_equipment_map:
                line_equipment_map[line] = []
            
            line_equipment_map[line].append(equipment_inst)
    
    # Log summary of equipment distribution for diagnosis
    pop_logger.info(f"Equipment distribution summary:")
    pop_logger.info(f"  • Total equipment found: {total_equipment_processed}")
    pop_logger.info(f"  • Equipment linked to lines: {total_equipment_with_line}")
    pop_logger.info(f"  • Equipment linked to equipment classes: {total_equipment_with_class}")
    pop_logger.info(f"  • Production lines with equipment: {len(line_equipment_map)}")
    
    # Process each line to establish equipment instance relationships
    total_relationships = 0
    line_relationship_counts: Dict[str, int] = {}
    
    # TKT-007: Track parallel relationships
    total_parallel_relationships = 0
    line_parallel_counts: Dict[str, int] = {}
    
    def safe_get_equipment_id(equipment: Thing) -> str:
        """Helper to safely get equipmentId or fallback to name for sorting."""
        equipment_id = getattr(equipment, prop_equipmentId.python_name, None)
        if equipment_id:
            return str(equipment_id)
        return equipment.name
    
    with onto:
        for line_ind, equipment_instances in line_equipment_map.items():
            line_id = getattr(line_ind, "lineId", line_ind.name)
            pop_logger.info(f"Processing equipment instance relationships for line: {line_id}")
            
            if not equipment_instances:
                pop_logger.debug(f"No equipment instances found for line: {line_id}")
                continue
            
            # Get instances with sequencePosition values
            equipment_with_positions = []
            equipment_without_positions = []
            
            # TKT-006: Enhanced collection of equipment with their sequence positions
            for equipment_inst in equipment_instances:
                # Get the equipment ID for consistent reference
                eq_id = safe_get_equipment_id(equipment_inst)
                
                # TKT-006: Get sequencePosition value for this equipment
                position = getattr(equipment_inst, prop_sequencePosition.python_name, None)
                
                # Get the equipment class for logging
                eq_class_ind = getattr(equipment_inst, prop_memberOfClass.python_name, None)
                eq_class_id = "Unknown"
                if eq_class_ind and prop_equipmentClassId:
                    eq_class_id = getattr(eq_class_ind, prop_equipmentClassId.python_name, eq_class_ind.name)
                
                if position is not None:
                    # Store equipment with sequence position information
                    equipment_with_positions.append((equipment_inst, position, eq_id))
                    pop_logger.debug(f"TKT-006: Equipment {eq_id} (class: {eq_class_id}) has sequencePosition: {position}")
                    total_equipment_with_sequence_position += 1
                else:
                    # Try to look up the position from its class using the config
                    if eq_class_ind and prop_equipmentClassId:
                        # Get class ID to look up in configuration
                        equipment_class_id = getattr(eq_class_ind, prop_equipmentClassId.python_name, eq_class_ind.name)
                        
                        # Try line-specific sequence first
                        if line_id in LINE_SPECIFIC_EQUIPMENT_SEQUENCE and equipment_class_id in LINE_SPECIFIC_EQUIPMENT_SEQUENCE[line_id]:
                            position = LINE_SPECIFIC_EQUIPMENT_SEQUENCE[line_id].get(equipment_class_id)
                            pop_logger.info(f"TKT-006: Found position {position} for {eq_id} using line-specific config for class {equipment_class_id}")
                            
                            # Set the position on the equipment individual - TKT-004: Pass context
                            _set_property_value(equipment_inst, prop_sequencePosition, position, is_functional=True, context=context)
                            equipment_with_positions.append((equipment_inst, position, eq_id))
                            total_equipment_with_sequence_position += 1
                            continue
                        
                        # Try default sequence as fallback
                        if equipment_class_id in DEFAULT_EQUIPMENT_SEQUENCE:
                            position = DEFAULT_EQUIPMENT_SEQUENCE.get(equipment_class_id)
                            pop_logger.info(f"TKT-006: Found position {position} for {eq_id} using default config for class {equipment_class_id}")
                            
                            # Set the position on the equipment individual - TKT-004: Pass context
                            _set_property_value(equipment_inst, prop_sequencePosition, position, is_functional=True, context=context)
                            equipment_with_positions.append((equipment_inst, position, eq_id))
                            total_equipment_with_sequence_position += 1
                            continue
                    
                    # If we get here, we couldn't find or set a position
                    equipment_without_positions.append((equipment_inst, eq_id))
                    pop_logger.warning(f"TKT-006: Equipment {eq_id} (class: {eq_class_id}) on line {line_id} has no sequencePosition and none could be determined.")
            
            # Step 2: Sort equipment instances by sequencePosition, then by equipmentId
            sorted_equipment = sorted(equipment_with_positions, key=lambda x: (x[1], x[2]))
            
            if not sorted_equipment:
                pop_logger.warning(f"No equipment with sequence positions found on line {line_id}. Skipping relationship setup.")
                lines_without_sequence.append(line_id)
                continue
            
            # Log the sorted equipment for verification
            pop_logger.info(f"TKT-006: Sorted equipment on line {line_id} (format: id [position]):")
            for i, (eq, pos, eq_id) in enumerate(sorted_equipment):
                pop_logger.info(f"  {i+1}. {eq_id} [{pos}]")
            
            # Step 3: Link equipment instances with isImmediatelyUpstreamOf/isImmediatelyDownstreamOf
            relationships_created = 0
            for i in range(len(sorted_equipment) - 1):
                upstream_eq, upstream_pos, up_id = sorted_equipment[i]
                downstream_eq, downstream_pos, down_id = sorted_equipment[i + 1]
                
                # Validate to ensure we're not creating self-references
                if upstream_eq is downstream_eq:
                    pop_logger.error(f"Detected self-reference attempt for equipment {up_id} on line {line_id}. Skipping this link.")
                    continue
                
                try:
                    # Create forward relationship (isImmediatelyUpstreamOf) - TKT-004: Pass context
                    _set_property_value(upstream_eq, prop_isImmediatelyUpstreamOf, downstream_eq, is_functional=False, context=context)
                    pop_logger.debug(f"TKT-006: Created relationship: {up_id} (pos {upstream_pos}) isImmediatelyUpstreamOf {down_id} (pos {downstream_pos})")
                    
                    # Create inverse relationship (isImmediatelyDownstreamOf) if property exists - TKT-004: Pass context
                    if prop_isImmediatelyDownstreamOf:
                        _set_property_value(downstream_eq, prop_isImmediatelyDownstreamOf, upstream_eq, is_functional=False, context=context)
                        pop_logger.debug(f"TKT-006: Created inverse relationship: {down_id} isImmediatelyDownstreamOf {up_id}")
                    
                    relationships_created += 1
                except Exception as e:
                    pop_logger.error(f"Error creating relationship between {up_id} and {down_id}: {e}")
            
            # Record relationships for this line
            if relationships_created > 0:
                line_relationship_counts[line_id] = relationships_created
                total_relationships += relationships_created
                pop_logger.info(f"Established {relationships_created} instance relationships for line {line_id}.")
            
            # TKT-007: Step 4: Identify and link parallel equipment (equipment with same sequence position)
            if prop_isParallelWith:
                # Group equipment by sequence position
                position_equipment_map = {}
                for eq, pos, eq_id in sorted_equipment:
                    if pos not in position_equipment_map:
                        position_equipment_map[pos] = []
                    position_equipment_map[pos].append((eq, eq_id))
                
                # Process each position group that has multiple equipment
                parallel_relationships = 0
                for pos, equipment_list in position_equipment_map.items():
                    if len(equipment_list) > 1:
                        pop_logger.info(f"TKT-007: Found {len(equipment_list)} parallel equipment at position {pos} on line {line_id}")
                        
                        # Link all equipment at this position with isParallelWith relationships
                        for i in range(len(equipment_list)):
                            for j in range(i+1, len(equipment_list)):
                                eq1, eq1_id = equipment_list[i]
                                eq2, eq2_id = equipment_list[j]
                                
                                # Validate to ensure we're not creating self-references
                                if eq1 is eq2:
                                    pop_logger.error(f"TKT-007: Detected self-reference attempt for parallel equipment {eq1_id} on line {line_id}. Skipping this link.")
                                    continue
                                
                                try:
                                    # Since isParallelWith is symmetric, we only need to set it in one direction
                                    # The OWL reasoner will infer the other direction - TKT-004: Pass context
                                    _set_property_value(eq1, prop_isParallelWith, eq2, is_functional=False, context=context)
                                    pop_logger.debug(f"TKT-007: Created parallel relationship: {eq1_id} isParallelWith {eq2_id} (position {pos})")
                                    parallel_relationships += 1
                                except Exception as e:
                                    pop_logger.error(f"TKT-007: Error creating parallel relationship between {eq1_id} and {eq2_id}: {e}")
                
                if parallel_relationships > 0:
                    line_parallel_counts[line_id] = parallel_relationships
                    total_parallel_relationships += parallel_relationships
                    pop_logger.info(f"TKT-007: Established {parallel_relationships} parallel equipment relationships for line {line_id}.")
            
            # Log info about equipment without positions
            if equipment_without_positions:
                pop_logger.warning(f"Line {line_id} has {len(equipment_without_positions)} equipment without sequence positions.")
                if len(equipment_without_positions) <= 10:
                    for eq_id in [eq_id for _, eq_id in equipment_without_positions]:
                        pop_logger.warning(f"  • Equipment without position: {eq_id}")
                else:
                    sample_ids = [eq_id for _, eq_id in equipment_without_positions[:5]]
                    pop_logger.warning(f"  • First 5 equipment without positions: {', '.join(sample_ids)}...")

    # Print summary report
    print("\n=== EQUIPMENT INSTANCE RELATIONSHIP REPORT ===")
    print(f"Found {total_equipment_with_sequence_position} equipment instances with sequencePosition")
    
    if total_relationships > 0:
        pop_logger.info(f"Established {total_relationships} equipment instance relationships across {len(line_relationship_counts)} production lines.")
        print(f"Established {total_relationships} equipment instance relationships on {len(line_relationship_counts)} lines:")
        for line_id, count in sorted(line_relationship_counts.items()):
            print(f"  • Line {line_id}: {count} relationships")

        # Print info about the sequencing approach
        print("\nInstance sequencing approach:")
        print("  • Equipment instances are sorted by sequencePosition, then by equipmentId")
        print("  • Sorted instances on the same line are linked via isImmediatelyUpstreamOf/isImmediatelyDownstreamOf")
    else:
        pop_logger.warning("No equipment instance relationships were established.")
        print("No equipment instance relationships could be established.")
        print("Possible reasons:")
        print("  • Equipment not linked to lines/classes")
        print("  • Missing sequencePosition values (check TKT-010 implementation)")
        print("  • No equipment found on the same line")
    
    # TKT-007: Print parallel relationship summary
    if prop_isParallelWith and total_parallel_relationships > 0:
        pop_logger.info(f"TKT-007: Established {total_parallel_relationships} parallel equipment relationships across {len(line_parallel_counts)} production lines.")
        print(f"\nEstablished {total_parallel_relationships} parallel equipment relationships on {len(line_parallel_counts)} lines:")
        for line_id, count in sorted(line_parallel_counts.items()):
            print(f"  • Line {line_id}: {count} parallel relationships")
        
        print("\nParallel equipment identification approach:")
        print("  • Equipment instances with the same sequencePosition on the same line are considered parallel")
        print("  • Parallel instances are linked via the symmetric isParallelWith relationship")
    elif prop_isParallelWith:
        pop_logger.info("TKT-007: No parallel equipment relationships were established.")
        print("\nNo parallel equipment relationships could be established.")
        print("Possible reasons:")
        print("  • No equipment instances with the same sequence position on the same line")
        print("  • Equipment lacking sequence position information")
    
    # Log lines without sequence
    if lines_without_sequence:
        print("\nProduction lines without sequence relationships:")
        for line_id in sorted(lines_without_sequence):
            print(f"  • {line_id}")
    
    # TKT-006: Add a summary log for the relationships created
    pop_logger.info(f"TKT-006: Successfully established {total_relationships} instance-level equipment relationships")
    
    # TKT-007: Add a summary log for the parallel relationships created
    if prop_isParallelWith:
        pop_logger.info(f"TKT-007: Successfully established {total_parallel_relationships} parallel equipment relationships")
    
    # TKT-004: Return the context along with the relationship count for property usage tracking
    return total_relationships, context
