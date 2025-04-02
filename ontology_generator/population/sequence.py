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

def setup_equipment_sequence_relationships(onto: Ontology,
                                          equipment_class_positions: Dict[str, int],
                                          defined_classes: Dict[str, ThingClass],
                                          defined_properties: Dict[str, PropertyClass],
                                          created_equipment_class_inds: Dict[str, Thing]):
    """
    Establish upstream/downstream relationships between equipment *classes* based on sequence positions.
    
    Args:
        onto: The ontology
        equipment_class_positions: Dictionary mapping equipment class names to sequence positions
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        created_equipment_class_inds: Dictionary mapping equipment class names to class individuals
    """
    pop_logger.info("Setting up CLASS-LEVEL equipment sequence relationships based on position...")

    # Get context for properties/classes
    context = PopulationContext(onto, defined_classes, defined_properties, {})  # is_functional map not needed here

    # Get the CLASS-LEVEL properties
    prop_classIsUpstreamOf = context.get_prop("classIsUpstreamOf")
    prop_classIsDownstreamOf = context.get_prop("classIsDownstreamOf")  # Optional for inverse

    if not prop_classIsUpstreamOf:
        pop_logger.error("Cannot establish CLASS-LEVEL sequence relationships: 'classIsUpstreamOf' property not defined.")
        return
    if not prop_classIsDownstreamOf:
        pop_logger.warning("'classIsDownstreamOf' inverse property not found. Only forward class relationships will be set.")

    cls_EquipmentClass = context.get_class("EquipmentClass")
    if not cls_EquipmentClass: 
        return  # Should have been caught earlier, but safe check

    # Verify domain/range compatibility (optional but good practice)
    if cls_EquipmentClass not in prop_classIsUpstreamOf.domain:
        pop_logger.warning(f"Property 'classIsUpstreamOf' ({prop_classIsUpstreamOf}) does not have EquipmentClass in its domain {prop_classIsUpstreamOf.domain}.")
    # Range check assumes list of classes is expected
    if not any(issubclass(cls_EquipmentClass, r_cls) for r_cls in (prop_classIsUpstreamOf.range if isinstance(prop_classIsUpstreamOf.range, list) else [prop_classIsUpstreamOf.range])):
        pop_logger.warning(f"Property 'classIsUpstreamOf' ({prop_classIsUpstreamOf}) does not have EquipmentClass in its range {prop_classIsUpstreamOf.range}.")


    if not created_equipment_class_inds:
        pop_logger.warning("No created EquipmentClass individuals provided. Cannot establish class relationships.")
        return
    if not equipment_class_positions:
        pop_logger.warning("Equipment class positions dictionary is empty. Cannot establish class relationships.")
        return

    # Sort classes by their position number (safely handling None values)
    sorted_classes = _safe_sort_by_position(equipment_class_positions.items())
    
    # Log position information for debugging
    pop_logger.debug("Equipment class positions for sequence setup:")
    for cls_name, pos in sorted_classes:
        pop_logger.debug(f"  Class: {cls_name}, Position: {pos}")

    if len(sorted_classes) < 2:
        pop_logger.warning("Not enough equipment classes with sequence positions (< 2) to establish relationships.")
        return

    # Create relationships based on sequence order
    relationships_created = 0
    with onto:
        for i in range(len(sorted_classes) - 1):
            upstream_class_name, up_pos = sorted_classes[i]
            downstream_class_name, down_pos = sorted_classes[i + 1]

            upstream_ind = created_equipment_class_inds.get(upstream_class_name)
            downstream_ind = created_equipment_class_inds.get(downstream_class_name)

            if not upstream_ind:
                pop_logger.warning(f"Sequence setup: Upstream class individual '{upstream_class_name}' not found in provided dict.")
                continue
            if not downstream_ind:
                pop_logger.warning(f"Sequence setup: Downstream class individual '{downstream_class_name}' not found in provided dict.")
                continue

            pop_logger.debug(f"Evaluating CLASS relationship: {upstream_ind.name} (Pos {up_pos}) -> {downstream_ind.name} (Pos {down_pos})")

            # Set relationships (classIsUpstreamOf is NON-functional per spec)
            try:
                # Use helper to check if relationship already exists before appending
                _set_property_value(upstream_ind, prop_classIsUpstreamOf, downstream_ind, is_functional=False)

                # Explicitly set the inverse relationship if available and needed
                if prop_classIsDownstreamOf:
                    _set_property_value(downstream_ind, prop_classIsDownstreamOf, upstream_ind, is_functional=False)

                # Check if the forward relationship was actually added (or already existed)
                if downstream_ind in getattr(upstream_ind, prop_classIsUpstreamOf.python_name, []):
                    relationships_created += 1  # Count successful links (new or existing is fine)
                    pop_logger.debug(f"Confirmed CLASS relationship: {upstream_class_name} classIsUpstreamOf {downstream_class_name}")

            except Exception as e:
                pop_logger.error(f"Error setting class relationship {upstream_class_name} -> {downstream_class_name}: {e}")

    pop_logger.info(f"Established/verified {relationships_created} CLASS-LEVEL upstream relationships.")

    # Print relationship summary to stdout
    print("\n=== EQUIPMENT CLASS SEQUENCE RELATIONSHIP REPORT ===")
    if relationships_created > 0:
        print(f"Established/verified {relationships_created} upstream relationships between Equipment Classes:")
        # Re-iterate to print the established sequence
        for i in range(len(sorted_classes) - 1):
            upstream_class_name, _ = sorted_classes[i]
            downstream_class_name, _ = sorted_classes[i + 1]
            # Check if both individuals exist to avoid errors if one was missing during linking
            if created_equipment_class_inds.get(upstream_class_name) and created_equipment_class_inds.get(downstream_class_name):
                print(f"  {upstream_class_name} → {downstream_class_name}")
    else:
        print("No class-level sequence relationships were created or verified.")
    print(f"Total classes with positions considered: {len(sorted_classes)}")


def setup_equipment_instance_relationships(onto: Ontology,
                                          defined_classes: Dict[str, ThingClass],
                                          defined_properties: Dict[str, PropertyClass],
                                          property_is_functional: Dict[str, bool],
                                          equipment_class_positions: Dict[str, int]):
    """
    Establish upstream/downstream relationships between equipment *instances* within the same production line.
    
    The approach:
    1. Group equipment instances by production line and equipment class
    2. For each line, sequence equipment classes based on the positions
       - Check for line-specific sequence configuration first
       - Fall back to global sequence positions if no line-specific config exists
    3. For each class on a line, sort its instances by equipmentId
    4. Chain instances within the same class sequentially
    5. Chain the last instance of one class to the first instance of the next class
    
    Args:
        onto: The ontology
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        property_is_functional: Dictionary indicating whether properties are functional
        equipment_class_positions: Dictionary mapping equipment class names to sequence positions
    """
    pop_logger.info("Setting up INSTANCE-LEVEL equipment relationships within production lines...")

    # Get context for properties/classes
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)

    # Get the required classes and properties
    cls_Equipment = context.get_class("Equipment")
    cls_ProductionLine = context.get_class("ProductionLine")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    prop_isPartOfProductionLine = context.get_prop("isPartOfProductionLine")
    prop_memberOfClass = context.get_prop("memberOfClass")
    prop_equipmentClassId = context.get_prop("equipmentClassId")  # Needed to get class name string
    prop_equipmentId = context.get_prop("equipmentId")  # Needed for sorting instances
    prop_equipment_isUpstreamOf = context.get_prop("equipmentIsUpstreamOf")
    prop_equipment_isDownstreamOf = context.get_prop("equipmentIsDownstreamOf")  # Optional for inverse

    # Check essentials
    if not all([cls_Equipment, cls_ProductionLine, cls_EquipmentClass,
                prop_isPartOfProductionLine, prop_memberOfClass, prop_equipmentClassId,
                prop_equipmentId, prop_equipment_isUpstreamOf]):
        pop_logger.error("Missing required classes or properties for equipment instance relationships.")
        return

    if not prop_equipment_isDownstreamOf:
        pop_logger.warning("'equipmentIsDownstreamOf' inverse property not found. Only forward instance relationships will be set.")

    if not equipment_class_positions:
        pop_logger.warning("Equipment class positions dictionary is empty. Cannot establish instance relationships.")
        return

    # Sort class names by position (safely handling None values)
    sorted_classes = _safe_sort_by_position(equipment_class_positions.items())
    sorted_class_names_by_pos = [item[0] for item in sorted_classes]
    
    # Log the sorted classes with their positions for better diagnostics
    pop_logger.info("Sorted equipment classes by sequence position:")
    for class_name, pos in sorted_classes:
        pop_logger.info(f"  • {class_name}: Position {pos}")

    if len(sorted_class_names_by_pos) < 1:  # Changed from 2 to 1 since we now chain within classes too
        pop_logger.warning("No equipment classes with sequence positions found. Cannot establish instance relationships.")
        return

    # Group equipment instances by line and class name
    pop_logger.debug("Grouping equipment instances by production line and class name...")
    line_equipment_map: Dict[Thing, Dict[str, List[Thing]]] = {}  # {line_individual: {class_name_str: [equipment_instances]}}
    # Track equipment classes without sequence position
    unsequenced_classes: Dict[str, List[str]] = {}  # {line_id: [class_names_without_position]}
    # Track lines with equipment but no sequence
    lines_without_sequence: List[str] = []

    # Iterate through all Equipment individuals in the ontology
    for equipment_inst in onto.search(type=cls_Equipment):
        # Get the line(s) this equipment belongs to (Non-functional)
        equipment_lines = getattr(equipment_inst, "isPartOfProductionLine", [])
        if not equipment_lines:
            pop_logger.debug(f"Equipment {equipment_inst.name} is not linked to any ProductionLine. Skipping.")
            continue

        # Get the EquipmentClass this equipment belongs to (Functional)
        equipment_class_ind = getattr(equipment_inst, "memberOfClass", None)
        if not equipment_class_ind or not isinstance(equipment_class_ind, cls_EquipmentClass):
            pop_logger.debug(f"Equipment {equipment_inst.name} is not linked to an EquipmentClass. Skipping.")
            continue

        # Get the class name string from the EquipmentClass individual (Functional)
        class_name_str = getattr(equipment_class_ind, "equipmentClassId", None)
        if not class_name_str:
            pop_logger.warning(f"EquipmentClass {equipment_class_ind.name} (linked from {equipment_inst.name}) is missing 'equipmentClassId'. Skipping.")
            continue

        # Check if this class name is in our sequence map
        has_position = class_name_str in equipment_class_positions

        # Add equipment to the map for each line it belongs to
        for equipment_line in equipment_lines:
            if not isinstance(equipment_line, cls_ProductionLine):
                pop_logger.warning(f"Equipment {equipment_inst.name} linked to non-ProductionLine '{equipment_line}'. Skipping this link.")
                continue
                
            # Get line ID for tracking
            line_id_str = getattr(equipment_line, "lineId", equipment_line.name)
            
            # Track classes without positions for diagnostics
            if not has_position:
                if line_id_str not in unsequenced_classes:
                    unsequenced_classes[line_id_str] = []
                if class_name_str not in unsequenced_classes[line_id_str]:
                    unsequenced_classes[line_id_str].append(class_name_str)
                    pop_logger.warning(f"Equipment class '{class_name_str}' on line {line_id_str} has no sequence position. " +
                                      f"Add this class to DEFAULT_EQUIPMENT_SEQUENCE or LINE_SPECIFIC_EQUIPMENT_SEQUENCE['{line_id_str}']")

            # Add equipment to the map structure
            if equipment_line not in line_equipment_map:
                line_equipment_map[equipment_line] = {cn: [] for cn in sorted_class_names_by_pos}  # Pre-initialize with sequenced classes
            # Ensure the specific class bucket exists (might not if class wasn't in initial sequence list but had a position)
            if class_name_str not in line_equipment_map[equipment_line]:
                line_equipment_map[equipment_line][class_name_str] = []

            if equipment_inst not in line_equipment_map[equipment_line][class_name_str]:
                line_equipment_map[equipment_line][class_name_str].append(equipment_inst)
                pop_logger.debug(f"Mapped Equipment {equipment_inst.name} to Line {equipment_line.name} under Class '{class_name_str}'")

    # Create instance-level relationships within each line
    total_relationships = 0
    line_relationship_counts: Dict[str, int] = {}
    pop_logger.info(f"Found {len(line_equipment_map)} lines with equipment.")

    def safe_get_equipment_id(equipment: Thing) -> str:
        """Helper to safely get equipmentId or fallback to name for sorting."""
        equipment_id = getattr(equipment, "equipmentId", None)
        if equipment_id:
            return str(equipment_id)
        return equipment.name

    with onto:
        for line_ind, class_equipment_map_on_line in line_equipment_map.items():
            line_id_str = getattr(line_ind, "lineId", line_ind.name)
            line_relationships = 0
            
            # Check for line-specific sequence configuration
            line_specific_sequence = LINE_SPECIFIC_EQUIPMENT_SEQUENCE.get(line_id_str)
            
            if line_specific_sequence:
                pop_logger.info(f"Using line-specific sequence configuration for line {line_id_str}")
                
                # Create a sorted list of class names based on the line-specific configuration
                line_sorted_classes = _safe_sort_by_position(line_specific_sequence.items())
                sorted_class_names_for_line = [item[0] for item in line_sorted_classes]
                
                # Log the line-specific sequence
                pos_str = ", ".join([f"{cls}:{pos}" for cls, pos in line_sorted_classes])
                pop_logger.info(f"Line-specific sequence for {line_id_str}: {pos_str}")
            else:
                # Use the default global sequence
                pop_logger.info(f"Using default sequence configuration for line {line_id_str}")
                sorted_class_names_for_line = sorted_class_names_by_pos
            
            # If no classes were found with positions, track this line
            if not sorted_class_names_for_line:
                lines_without_sequence.append(line_id_str)
                pop_logger.warning(f"Line {line_id_str} has equipment but no sequence could be established. Skipping.")
                continue
                
            pop_logger.info(f"Processing equipment instance relationships for line: {line_id_str}")

            # Track the last instance in the chain to link between classes
            last_instance_in_chain = None

            # Process each equipment class in sequence order specific to this line
            for class_name in sorted_class_names_for_line:
                equipment_instances = class_equipment_map_on_line.get(class_name, [])

                if not equipment_instances:
                    pop_logger.debug(f"No instances of '{class_name}' found on line {line_id_str}. Continuing to next class.")
                    continue  # No instances for this class on this line, but keep last_instance_in_chain

                # Sort equipment instances by equipmentId for sequential chaining
                sorted_instances = sorted(equipment_instances, key=safe_get_equipment_id)

                # Log the instances being chained
                instance_ids = [safe_get_equipment_id(e) for e in sorted_instances]
                pop_logger.info(f"Chaining {len(sorted_instances)} instances of '{class_name}' on line '{line_id_str}' by equipmentId: {', '.join(instance_ids)}")

                # If there's a previous class's last instance, link it to the first instance of this class
                if last_instance_in_chain:
                    try:
                        # Link the last instance of previous class to first instance of current class
                        _set_property_value(last_instance_in_chain, prop_equipment_isUpstreamOf, sorted_instances[0], is_functional=False)

                        # Set the inverse relation if available
                        if prop_equipment_isDownstreamOf:
                            _set_property_value(sorted_instances[0], prop_equipment_isDownstreamOf, last_instance_in_chain, is_functional=False)

                        line_relationships += 1
                        prev_class = getattr(last_instance_in_chain.memberOfClass, "equipmentClassId", "Unknown")
                        pop_logger.info(f"Linked end of '{prev_class}' chain ({safe_get_equipment_id(last_instance_in_chain)}) " +
                                        f"to start of '{class_name}' chain ({safe_get_equipment_id(sorted_instances[0])}) on line '{line_id_str}'")
                    except Exception as e:
                        pop_logger.error(f"Error linking between class chains on line {line_id_str}: {e}")

                # Chain instances within this class sequentially
                if len(sorted_instances) > 1:  # Only need to chain if there are multiple instances
                    internal_links = 0
                    for i in range(len(sorted_instances) - 1):
                        try:
                            upstream_eq = sorted_instances[i]
                            downstream_eq = sorted_instances[i + 1]

                            # Create forward relationship
                            _set_property_value(upstream_eq, prop_equipment_isUpstreamOf, downstream_eq, is_functional=False)

                            # Create inverse relationship if property exists
                            if prop_equipment_isDownstreamOf:
                                _set_property_value(downstream_eq, prop_equipment_isDownstreamOf, upstream_eq, is_functional=False)

                            line_relationships += 1
                            internal_links += 1

                            # Debug level for internal chainings as there could be many
                            pop_logger.debug(f"Chained {class_name} instances: {safe_get_equipment_id(upstream_eq)} → {safe_get_equipment_id(downstream_eq)}")
                        except Exception as e:
                            pop_logger.error(f"Error chaining instances within {class_name} on line {line_id_str}: {e}")

                    if internal_links > 0:
                        pop_logger.info(f"Created {internal_links} internal chain links among {class_name} instances on line {line_id_str}")

                # Update last_instance_in_chain to the last instance of the current class
                last_instance_in_chain = sorted_instances[-1]

            # Record relationships for this line
            if line_relationships > 0:
                line_relationship_counts[line_id_str] = line_relationships
                total_relationships += line_relationships
                pop_logger.info(f"Established/verified {line_relationships} instance relationships for line {line_id_str}.")

    # Print summary report
    print("\n=== EQUIPMENT INSTANCE RELATIONSHIP REPORT ===")
    if total_relationships > 0:
        pop_logger.info(f"Established/verified {total_relationships} equipment instance relationships across {len(line_relationship_counts)} production lines.")
        print(f"Established/verified {total_relationships} equipment instance relationships on {len(line_relationship_counts)} lines:")
        for line_id_str, count in sorted(line_relationship_counts.items()):
            print(f"  Line {line_id_str}: {count} relationships")

        # Print info about the chaining approach
        print("\nChaining approach:")
        print("  • Equipment instances of the same class are chained in sequence by their equipmentId")
        print("  • Last instance of each class is linked to first instance of the next class in sequence")
        print("  • Class sequence is determined by:")
        print("    - Line-specific configuration (if available in LINE_SPECIFIC_EQUIPMENT_SEQUENCE)")
        print("    - Global DEFAULT_EQUIPMENT_SEQUENCE configuration (fallback)")
    else:
        pop_logger.warning("No equipment instance relationships were created or verified.")
        print("No equipment instance relationships could be established or verified.")
        print("Possible reasons: Equipment not linked to lines/classes, missing sequence positions, or no equipment found on the same line.")
        
    # Report sequence analysis issues
    if unsequenced_classes:
        print("\n=== EQUIPMENT SEQUENCE DIAGNOSTIC ISSUES ===")
        print(f"Found {sum(len(classes) for classes in unsequenced_classes.values())} equipment classes without sequence positions:")
        for line_id, classes in sorted(unsequenced_classes.items()):
            print(f"  Line {line_id}: {', '.join(sorted(classes))}")
            
    if lines_without_sequence:
        if not unsequenced_classes:  # Only print header if not already printed
            print("\n=== EQUIPMENT SEQUENCE DIAGNOSTIC ISSUES ===")
        print(f"Found {len(lines_without_sequence)} lines with equipment but no sequence established:")
        for line_id in sorted(lines_without_sequence):
            print(f"  Line {line_id}")
        
    print("\n---")
