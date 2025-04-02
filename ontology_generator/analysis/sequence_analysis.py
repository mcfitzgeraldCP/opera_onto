"""
Sequence Analysis Module for the Ontology Generator.

This module provides functions for analyzing equipment sequences in the ontology.
"""
from typing import List, Optional, Dict, Any, Tuple
from owlready2 import Thing, Ontology

from ontology_generator.utils.logging import analysis_logger

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
    for ind in onto.individuals():
        # Check if it's a ProductionLine by looking for lineId property
        if hasattr(ind, "lineId"):
            lines.append(ind)
    
    if not lines:
        analysis_logger.warning("No production lines found in ontology")
        return "No production lines found in ontology"
    
    analysis_logger.info(f"Found {len(lines)} production lines")
    
    report_lines = []
    report_lines.append("\n=== EQUIPMENT SEQUENCE REPORT ===")
    
    # Sort lines by lineId for consistent output
    lines.sort(key=lambda l: getattr(l, "lineId", l.name))
    
    for line in lines:
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
        - Dictionary with sequence statistics
    """
    analysis_logger.info("Analyzing equipment sequences in ontology")
    
    # Find all production lines
    lines = []
    for ind in onto.individuals():
        if hasattr(ind, "lineId"):
            lines.append(ind)
    
    if not lines:
        analysis_logger.warning("No production lines found in ontology")
        return {}, {}
    
    # Generate sequences for each line
    sequences = {}
    stats = {"total_lines": len(lines), "lines_with_sequence": 0, "total_equipment": 0, "class_counts": {}}
    
    for line in lines:
        line_id = getattr(line, "lineId", line.name)
        sequence = get_equipment_sequence_for_line(onto, line)
        
        if sequence:
            sequences[line_id] = sequence
            stats["lines_with_sequence"] += 1
            stats["total_equipment"] += len(sequence)
            
            # Count equipment by class
            for eq in sequence:
                eq_class = "Unknown"
                if hasattr(eq, "memberOfClass") and eq.memberOfClass:
                    if hasattr(eq.memberOfClass, "equipmentClassId"):
                        eq_class = eq.memberOfClass.equipmentClassId
                
                if eq_class not in stats["class_counts"]:
                    stats["class_counts"][eq_class] = 0
                stats["class_counts"][eq_class] += 1
    
    analysis_logger.info(f"Analysis complete. Found sequences for {stats['lines_with_sequence']} of {stats['total_lines']} lines")
    return sequences, stats 