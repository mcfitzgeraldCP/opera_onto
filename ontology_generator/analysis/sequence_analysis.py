"""
Sequence Analysis Module for the Ontology Generator.

This module provides functions for analyzing equipment sequences in the ontology.
"""
from typing import List, Optional, Dict, Any, Tuple
from owlready2 import Thing, Ontology

from ontology_generator.utils.logging import analysis_logger

def _safe_sort_by_attribute(items, attr_name, default_value="Unknown"):
    """
    Safely sorts items by an attribute, handling None values gracefully.
    
    Args:
        items: List of objects to sort
        attr_name: Name of attribute to sort by
        default_value: Default value to use for None attributes
        
    Returns:
        Sorted list of items
    """
    def get_safe_attribute(item):
        value = getattr(item, attr_name, None)
        if value is None:
            value = getattr(item, "name", default_value)
            if value is None:
                analysis_logger.warning(f"Item has neither {attr_name} nor name attribute, using default value for sorting")
                return default_value
        return value
        
    return sorted(items, key=get_safe_attribute)

def get_equipment_sequence_for_line(onto: Ontology, line_individual: Thing) -> List[Thing]:
    """
    Retrieves the equipment sequence for a specific production line.
    
    Args:
        onto: The ontology object
        line_individual: The ProductionLine individual
        
    Returns:
        A list of equipment individuals in sequence order
    """
    # Get required properties
    equipment_is_upstream_of = None
    for prop in onto.object_properties():
        if prop.name == "equipmentIsUpstreamOf":
            equipment_is_upstream_of = prop
            break
    
    if not equipment_is_upstream_of:
        analysis_logger.warning("Property 'equipmentIsUpstreamOf' not found in ontology")
        return []
    
    # Get all equipment on this line
    equipment_on_line = []
    for ind in onto.individuals():
        if hasattr(ind, "isPartOfProductionLine"):
            line_list = ind.isPartOfProductionLine
            if not isinstance(line_list, list):
                line_list = [line_list] if line_list else []
            
            if line_individual in line_list:
                equipment_on_line.append(ind)
    
    if not equipment_on_line:
        analysis_logger.info(f"No equipment found for line {line_individual.name}")
        return []
        
    analysis_logger.info(f"Found {len(equipment_on_line)} equipment instances on line {line_individual.name}")
    
    # Find equipment with no upstream equipment (start of sequence)
    start_equipment = []
    for eq in equipment_on_line:
        has_upstream = False
        for other_eq in equipment_on_line:
            upstream_list = getattr(other_eq, equipment_is_upstream_of.python_name, [])
            if not isinstance(upstream_list, list):
                upstream_list = [upstream_list] if upstream_list else []
                
            if eq in upstream_list:
                has_upstream = True
                break
        if not has_upstream:
            start_equipment.append(eq)
    
    analysis_logger.info(f"Found {len(start_equipment)} starting equipment (no upstream) for line {line_individual.name}")
    
    # Build sequence by following relationships
    sequence = []
    visited = set()
    
    def follow_sequence(eq):
        if eq in visited:
            return
        visited.add(eq)
        sequence.append(eq)
        
        downstream_list = getattr(eq, equipment_is_upstream_of.python_name, [])
        if not isinstance(downstream_list, list):
            downstream_list = [downstream_list] if downstream_list else []
        
        # Filter to equipment on this line only
        downstream_list = [d for d in downstream_list if d in equipment_on_line]
        
        # Sort by equipment ID if multiple downstream (unlikely but possible)
        if len(downstream_list) > 1:
            downstream_list.sort(key=lambda e: getattr(e, "equipmentId", e.name))
        
        for downstream in downstream_list:
            follow_sequence(downstream)
    
    # Start from each entry point
    for eq in start_equipment:
        follow_sequence(eq)
    
    analysis_logger.info(f"Determined sequence with {len(sequence)} equipment for line {line_individual.name}")
    return sequence

def generate_equipment_sequence_report(onto: Ontology) -> str:
    """
    Generates a report of equipment sequences for all lines in the ontology.
    
    Args:
        onto: The ontology object
        
    Returns:
        A string report of all equipment sequences
    """
    analysis_logger.info("Generating equipment sequence report for all lines")
    
    # Find all production lines
    lines = []
    
    # Get the ProductionLine class - search by name
    production_line_class = None
    for cls in onto.classes():
        if cls.name == "ProductionLine":
            production_line_class = cls
            break
    
    if not production_line_class:
        analysis_logger.warning("ProductionLine class not found in ontology - trying to find lines by lineId property")
        # Fallback to property-based detection with warnings about duplicates
        line_ids_seen = set()
        for ind in onto.individuals():
            if hasattr(ind, "lineId"):
                line_id = getattr(ind, "lineId")
                if line_id in line_ids_seen:
                    analysis_logger.warning(f"Duplicate lineId found: {line_id} - possible data quality issue")
                else:
                    line_ids_seen.add(line_id)
                    lines.append(ind)
    else:
        # Use proper class-based detection
        for ind in onto.individuals():
            if isinstance(ind, production_line_class):
                lines.append(ind)
    
    if not lines:
        analysis_logger.warning("No production lines found in ontology")
        return "No production lines found in ontology"
    
    analysis_logger.info(f"Found {len(lines)} production lines")
    
    # Log some line IDs for verification
    sample_size = min(5, len(lines))
    sample_lines = lines[:sample_size]
    sample_ids = [getattr(line, "lineId", line.name) for line in sample_lines]
    analysis_logger.info(f"Sample line IDs: {', '.join(map(str, sample_ids))}")
    
    report_lines = []
    report_lines.append("\n=== EQUIPMENT SEQUENCE REPORT ===")
    
    # Use safe sort for lines to avoid None comparison errors
    try:
        sorted_lines = _safe_sort_by_attribute(lines, "lineId")
    except Exception as e:
        analysis_logger.error(f"Error sorting lines: {e} - using unsorted lines")
        sorted_lines = lines
    
    for line in sorted_lines:
        line_id = getattr(line, "lineId", line.name)
        report_lines.append(f"\nLine: {line_id}")
        
        # Get sequence for this line
        sequence = get_equipment_sequence_for_line(onto, line)
        
        if not sequence:
            report_lines.append("  No equipment sequence found")
            continue
        
        # List equipment in sequence
        for i, eq in enumerate(sequence, 1):
            eq_id = getattr(eq, "equipmentId", "Unknown")
            eq_name = getattr(eq, "equipmentName", eq.name)
            eq_class = "Unknown"
            
            # Get class information
            if hasattr(eq, "memberOfClass") and eq.memberOfClass:
                if hasattr(eq.memberOfClass, "equipmentClassId"):
                    eq_class = eq.memberOfClass.equipmentClassId
            
            report_lines.append(f"  {i}. {eq_id} ({eq_name}) - Class: {eq_class}")
    
    return "\n".join(report_lines)

def analyze_equipment_sequences(onto: Ontology) -> Tuple[Dict[str, List[Thing]], Dict[str, Dict[str, Any]]]:
    """
    Analyzes all equipment sequences in the ontology and returns detailed information.
    
    Args:
        onto: The ontology object
        
    Returns:
        Tuple containing:
        - Dictionary mapping line IDs to equipment sequences
        - Dictionary with sequence statistics and diagnostics
    """
    analysis_logger.info("Analyzing equipment sequences in ontology")
    
    # Find all production lines using class-based detection
    lines = []
    
    # Get the ProductionLine class
    production_line_class = None
    for cls in onto.classes():
        if cls.name == "ProductionLine":
            production_line_class = cls
            break
    
    if production_line_class:
        for ind in onto.individuals():
            if isinstance(ind, production_line_class):
                lines.append(ind)
    else:
        # Fallback to property-based detection
        analysis_logger.warning("ProductionLine class not found in ontology - using lineId property")
        for ind in onto.individuals():
            if hasattr(ind, "lineId"):
                lines.append(ind)
    
    if not lines:
        analysis_logger.warning("No production lines found in ontology")
        return {}, {"error": "No production lines found"}
    
    # Get essential ontology elements
    equipment_class = None
    for cls in onto.classes():
        if cls.name == "Equipment":
            equipment_class = cls
            break
            
    if not equipment_class:
        analysis_logger.warning("Equipment class not found in ontology")
        return {}, {"error": "Equipment class not found"}
        
    # Get the "equipmentIsUpstreamOf" property
    equipment_is_upstream_of = None
    for prop in onto.object_properties():
        if prop.name == "equipmentIsUpstreamOf":
            equipment_is_upstream_of = prop
            break
            
    # Generate sequences for each line
    sequences = {}
    stats = {
        "total_lines": len(lines), 
        "lines_with_sequence": 0,
        "lines_without_sequence": 0,
        "total_equipment": 0, 
        "class_counts": {},
        "lines_with_equipment_but_no_sequence": [],
        "classes_without_sequence_position": set(),
        "equipment_without_sequence_by_line": {}
    }
    
    # Get all equipment individuals
    all_equipment = list(onto.search(type=equipment_class))
    stats["total_equipment"] = len(all_equipment)
    
    # Track equipment classes and their sequence positions
    class_sequence_positions = {}
    for equip in all_equipment:
        if hasattr(equip, "memberOfClass") and equip.memberOfClass:
            class_ind = equip.memberOfClass
            class_id = getattr(class_ind, "equipmentClassId", class_ind.name)
            
            # Count equipment by class
            if class_id not in stats["class_counts"]:
                stats["class_counts"][class_id] = 0
            stats["class_counts"][class_id] += 1
            
            # Check sequence position
            if class_id not in class_sequence_positions:
                position = getattr(class_ind, "defaultSequencePosition", None)
                class_sequence_positions[class_id] = position
                if position is None:
                    stats["classes_without_sequence_position"].add(class_id)
    
    # Process each line
    for line in lines:
        line_id = getattr(line, "lineId", line.name)
        line_id_str = str(line_id[0]) if isinstance(line_id, list) and line_id else str(line_id)
        sequence = get_equipment_sequence_for_line(onto, line)
        
        # Map line ID to its equipment sequence
        sequences[line_id_str] = sequence
        
        # Track equipment on this line that don't have a sequence
        equipment_on_line = []
        for equip in all_equipment:
            if hasattr(equip, "isPartOfProductionLine"):
                lines_list = equip.isPartOfProductionLine
                if not isinstance(lines_list, list):
                    lines_list = [lines_list] if lines_list else []
                    
                if line in lines_list:
                    equipment_on_line.append(equip)
        
        # Check if this line has equipment but no sequence
        if equipment_on_line and not sequence:
            stats["lines_without_sequence"] += 1
            stats["lines_with_equipment_but_no_sequence"].append(line_id_str)
            
            # Track equipment on this line without a sequence link
            stats["equipment_without_sequence_by_line"][line_id_str] = []
            for equip in equipment_on_line:
                # Get class information
                class_name = "Unknown"
                if hasattr(equip, "memberOfClass") and equip.memberOfClass:
                    class_name = getattr(equip.memberOfClass, "equipmentClassId", equip.memberOfClass.name)
                
                # Add to the list
                equip_id = getattr(equip, "equipmentId", equip.name)
                stats["equipment_without_sequence_by_line"][line_id_str].append({
                    "id": equip_id,
                    "name": getattr(equip, "equipmentName", equip.name),
                    "class": class_name,
                    "class_has_position": class_name in class_sequence_positions and class_sequence_positions[class_name] is not None
                })
        
        # Add to statistics
        if sequence:
            stats["lines_with_sequence"] += 1
            
    # Add sequence position information to statistics
    stats["classes_with_position"] = sum(1 for pos in class_sequence_positions.values() if pos is not None)
    stats["classes_without_position"] = sum(1 for pos in class_sequence_positions.values() if pos is None)
    stats["class_positions"] = {cls: pos for cls, pos in class_sequence_positions.items() if pos is not None}
    
    # Convert set to list for JSON serialization
    stats["classes_without_sequence_position"] = list(stats["classes_without_sequence_position"])
    
    analysis_logger.info(f"Sequence analysis complete: {stats['lines_with_sequence']} lines with sequences, "
                          f"{stats['lines_without_sequence']} lines without sequences, "
                          f"{len(stats['classes_without_sequence_position'])} classes without positions")
    
    return sequences, stats

def generate_enhanced_sequence_report(onto: Ontology) -> str:
    """
    Generates an enhanced report of equipment sequences and related issues.
    
    Args:
        onto: The ontology object
        
    Returns:
        A string with the enhanced sequence report
    """
    # Get sequence data and statistics
    sequences, stats = analyze_equipment_sequences(onto)
    
    # Build report
    report_lines = []
    report_lines.append("\n=== ENHANCED EQUIPMENT SEQUENCE REPORT ===")
    
    # Summary statistics
    report_lines.append(f"\nSUMMARY STATISTICS:")
    report_lines.append(f"  Total production lines: {stats['total_lines']}")
    report_lines.append(f"  Lines with equipment sequences: {stats['lines_with_sequence']}")
    report_lines.append(f"  Lines with equipment but no sequence: {len(stats.get('lines_with_equipment_but_no_sequence', []))}")
    report_lines.append(f"  Total equipment instances: {stats['total_equipment']}")
    report_lines.append(f"  Equipment classes without sequence positions: {len(stats.get('classes_without_sequence_position', []))}")
    
    # Class sequence positions
    report_lines.append(f"\nEQUIPMENT CLASS SEQUENCE POSITIONS:")
    for cls, pos in sorted(stats.get('class_positions', {}).items(), key=lambda x: x[1]):
        report_lines.append(f"  {cls}: Position {pos}")
    
    # Classes without positions
    if stats.get('classes_without_sequence_position'):
        report_lines.append(f"\nEQUIPMENT CLASSES WITHOUT SEQUENCE POSITIONS:")
        for cls in sorted(stats.get('classes_without_sequence_position', [])):
            report_lines.append(f"  {cls}")
    
    # Lines with equipment but no sequence
    if stats.get('lines_with_equipment_but_no_sequence'):
        report_lines.append(f"\nLINES WITH EQUIPMENT BUT NO SEQUENCE ESTABLISHED:")
        for line_id in sorted(stats.get('lines_with_equipment_but_no_sequence', [])):
            report_lines.append(f"  Line {line_id}:")
            equip_list = stats.get('equipment_without_sequence_by_line', {}).get(line_id, [])
            for eq in equip_list:
                class_status = "No position" if not eq['class_has_position'] else "Has position"
                report_lines.append(f"    {eq['id']} ({eq['name']}) - Class: {eq['class']} ({class_status})")
    
    # Equipment sequences by line
    report_lines.append(f"\nEQUIPMENT SEQUENCES BY LINE:")
    for line_id, sequence in sorted(sequences.items()):
        report_lines.append(f"\nLine: {line_id}")
        
        if not sequence:
            report_lines.append("  No equipment sequence found")
            continue
        
        # List equipment in sequence
        for i, eq in enumerate(sequence, 1):
            eq_id = getattr(eq, "equipmentId", "Unknown")
            eq_name = getattr(eq, "equipmentName", eq.name)
            eq_class = "Unknown"
            
            # Get class information
            if hasattr(eq, "memberOfClass") and eq.memberOfClass:
                if hasattr(eq.memberOfClass, "equipmentClassId"):
                    eq_class = eq.memberOfClass.equipmentClassId
            
            report_lines.append(f"  {i}. {eq_id} ({eq_name}) - Class: {eq_class}")
    
    return "\n".join(report_lines) 