#!/usr/bin/env python3
"""
Test module for verifying equipment class parsing and sequential chaining.

This script creates a synthetic ontology with test data to verify:
1. Equipment classes are parsed correctly (e.g., CaseFormer2 -> CaseFormer)
2. Instances of the same class on the same line are chained sequentially
3. Classes are linked in the correct sequence based on DEFAULT_EQUIPMENT_SEQUENCE
4. Lines with missing equipment types are handled correctly
"""

import logging
import sys
from typing import Dict, List, Tuple, Optional, Any, Set
from owlready2 import *
import re

# Import the functions we need to test
from create_ontology_V4_refactor import (
    parse_equipment_class,
    DEFAULT_EQUIPMENT_SEQUENCE, 
    PopulationContext,
    get_or_create_individual,
    _set_property_value,
    setup_equipment_instance_relationships
)

# Define a test version of DEFAULT_EQUIPMENT_SEQUENCE
DEFAULT_EQUIPMENT_SEQUENCE = {
    "Filler": 10, 
    "Labeler": 20,
    "CaseFormer": 30,
    "CaseSealer": 40,
    "Palletizer": 50
}

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
test_logger = logging.getLogger("test_equipment_chaining")
test_logger.setLevel(logging.DEBUG)

# Add a handler to output to console for clearer test output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
test_logger.addHandler(console_handler)

# Create a function to mimic the pop_logger from the main script
pop_logger = test_logger

# Test data for equipment names and expected class names
TEST_EQUIPMENT_NAMES = [
    # Standard cases
    ("FIPCO009_Filler", "Filler"),
    ("FIPCO009_Filler2", "Filler"),
    ("FIPCO009_CaseFormer3", "CaseFormer"),
    ("FIPCO009_Capper1", "Capper"),
    ("FIPCO009_Capper2", "Capper"),
    # Edge cases
    ("FIPCO009_123", "FIPCO009"),  # All digits after underscore
    ("CaseFormer2", "CaseFormer"),  # No underscore but with trailing digits
    ("Labeler", "Labeler"),        # No underscore, no digits
    ("", None),                    # Empty string
    (None, None),                  # None value
    ("123", "123"),                # All digits
]

def test_parse_equipment_class():
    """Test the parse_equipment_class function with various equipment names."""
    print("\n=== TESTING EQUIPMENT CLASS PARSING ===")
    
    for eq_name, expected_class in TEST_EQUIPMENT_NAMES:
        result = parse_equipment_class(eq_name)
        match = result == expected_class
        status = "✅" if match else "❌"
        print(f"{status} {eq_name!r:<20} -> {result!r:<15} (Expected: {expected_class!r})")

def create_test_ontology():
    """Create a test ontology with classes and properties needed for testing."""
    # Create a new ontology in memory
    onto = get_ontology("http://test.equipment.chaining.org/onto.owl")
    
    with onto:
        # Create required classes
        cls_Equipment = types.new_class("Equipment", (Thing,))
        cls_EquipmentClass = types.new_class("EquipmentClass", (Thing,))
        cls_ProductionLine = types.new_class("ProductionLine", (Thing,))
        
        # Create required properties
        prop_isPartOfProductionLine = types.new_class("isPartOfProductionLine", (ObjectProperty,))
        prop_isPartOfProductionLine.domain = [cls_Equipment]
        prop_isPartOfProductionLine.range = [cls_ProductionLine]
        
        prop_memberOfClass = types.new_class("memberOfClass", (ObjectProperty, FunctionalProperty,))
        prop_memberOfClass.domain = [cls_Equipment]
        prop_memberOfClass.range = [cls_EquipmentClass]
        
        prop_equipmentId = types.new_class("equipmentId", (DataProperty, FunctionalProperty,))
        prop_equipmentId.domain = [cls_Equipment]
        prop_equipmentId.range = [str]
        
        prop_equipmentClassId = types.new_class("equipmentClassId", (DataProperty, FunctionalProperty,))
        prop_equipmentClassId.domain = [cls_EquipmentClass]
        prop_equipmentClassId.range = [str]
        
        prop_lineId = types.new_class("lineId", (DataProperty, FunctionalProperty,))
        prop_lineId.domain = [cls_ProductionLine]
        prop_lineId.range = [str]
        
        # Create relationship properties for equipment sequencing
        prop_equipment_isUpstreamOf = types.new_class("equipmentIsUpstreamOf", (ObjectProperty,))
        prop_equipment_isUpstreamOf.domain = [cls_Equipment]
        prop_equipment_isUpstreamOf.range = [cls_Equipment]
        
        prop_equipment_isDownstreamOf = types.new_class("equipmentIsDownstreamOf", (ObjectProperty,))
        prop_equipment_isDownstreamOf.domain = [cls_Equipment]
        prop_equipment_isDownstreamOf.range = [cls_Equipment]
        prop_equipment_isDownstreamOf.inverse_property = prop_equipment_isUpstreamOf
    
    return onto

def create_test_equipment(onto, line_configs):
    """
    Create test equipment instances for testing chaining.
    
    Args:
        onto: The ontology to populate
        line_configs: Configuration of lines and their equipment
        
    Returns:
        Tuple of:
        - Dictionary mapping class names to their ThingClass objects
        - Dictionary mapping property names to their PropertyClass objects
        - Dictionary mapping property names to boolean indicating if they're functional
        - Dictionary mapping equipment class names to their position in the sequence
    """
    # Get required classes and properties
    classes = {
        "Equipment": onto.Equipment,
        "EquipmentClass": onto.EquipmentClass,
        "ProductionLine": onto.ProductionLine
    }
    
    properties = {
        "isPartOfProductionLine": onto.isPartOfProductionLine,
        "memberOfClass": onto.memberOfClass,
        "equipmentId": onto.equipmentId,
        "equipmentClassId": onto.equipmentClassId,
        "lineId": onto.lineId,
        "equipmentIsUpstreamOf": onto.equipmentIsUpstreamOf,
        "equipmentIsDownstreamOf": onto.equipmentIsDownstreamOf
    }
    
    # Track which properties are functional
    prop_is_functional = {
        "isPartOfProductionLine": False,
        "memberOfClass": True,
        "equipmentId": True,
        "equipmentClassId": True,
        "lineId": True,
        "equipmentIsUpstreamOf": False,
        "equipmentIsDownstreamOf": False
    }
    
    context = PopulationContext(onto, classes, properties, prop_is_functional)
    
    # Create production lines
    lines = {}
    for line_id in line_configs:
        line_ind = get_or_create_individual(classes["ProductionLine"], f"Line_{line_id}", onto)
        line_ind.lineId = line_id
        lines[line_id] = line_ind
    
    # Create equipment classes
    class_instances = {}
    for class_name, position in DEFAULT_EQUIPMENT_SEQUENCE.items():
        class_ind = get_or_create_individual(classes["EquipmentClass"], class_name, onto)
        class_ind.equipmentClassId = class_name
        class_instances[class_name] = class_ind
    
    # Create equipment instances for each line based on configurations
    equipment_instances = {}
    
    for line_id, equipment_list in line_configs.items():
        line_ind = lines[line_id]
        line_equipment = []
        
        for eq_info in equipment_list:
            eq_name = eq_info["name"]
            eq_id = eq_info["id"]
            
            # Get the correct class name using our parse function
            class_name = parse_equipment_class(eq_name)
            if not class_name:
                test_logger.warning(f"Could not parse class name from {eq_name}")
                continue
            
            # Get or create the class individual
            if class_name not in class_instances:
                class_ind = get_or_create_individual(classes["EquipmentClass"], class_name, onto)
                class_ind.equipmentClassId = class_name
                class_instances[class_name] = class_ind
            else:
                class_ind = class_instances[class_name]
            
            # Create the equipment instance
            eq_ind = get_or_create_individual(classes["Equipment"], f"Equipment_{eq_id}", onto)
            eq_ind.equipmentId = eq_id
            
            # Link equipment to its class
            _set_property_value(eq_ind, properties["memberOfClass"], class_ind, True)
            
            # Link equipment to its line
            _set_property_value(eq_ind, properties["isPartOfProductionLine"], line_ind, False)
            
            line_equipment.append(eq_ind)
            equipment_instances[eq_id] = eq_ind
            
            test_logger.info(f"Created equipment {eq_id} of class {class_name} on line {line_id}")
    
    # Return class positions for sequence generation
    return classes, properties, prop_is_functional, DEFAULT_EQUIPMENT_SEQUENCE

def verify_equipment_chains(onto):
    """
    Verify the equipment chains created in the ontology.
    
    Checks:
    1. Instances of same class are chained correctly
    2. Classes are chained according to DEFAULT_EQUIPMENT_SEQUENCE
    3. Lines with missing equipment types handle the gaps correctly
    """
    print("\n=== VERIFYING EQUIPMENT CHAINS ===")
    
    # Get all production lines
    lines = list(onto.search(type=onto.ProductionLine))
    
    for line in lines:
        line_id = getattr(line, "lineId", line.name)
        print(f"\nChecking chain for line: {line_id}")
        
        # Get all equipment on this line
        line_equipment = list(onto.search(isPartOfProductionLine=line))
        
        # Group equipment by class
        equipment_by_class = {}
        for eq in line_equipment:
            eq_class = getattr(eq, "memberOfClass", None)
            if not eq_class:
                continue
                
            class_name = getattr(eq_class, "equipmentClassId", None)
            if not class_name:
                continue
                
            if class_name not in equipment_by_class:
                equipment_by_class[class_name] = []
            equipment_by_class[class_name].append(eq)
        
        # Print the chain for this line
        checked_instances = set()
        
        # Find a starting point - equipment without upstream
        start_candidates = []
        for eq in line_equipment:
            upstream_count = len(getattr(eq, "equipmentIsDownstreamOf", []))
            if upstream_count == 0:
                start_candidates.append(eq)
        
        if not start_candidates:
            print(f"  No start point found for line {line_id}!")
            continue
            
        # Trace the chain from each starting point
        for start_eq in start_candidates:
            trace_equipment_chain(onto, start_eq, checked_instances, 0)
        
        # Check if we missed any equipment
        unchecked = [eq for eq in line_equipment if eq not in checked_instances]
        if unchecked:
            print(f"  Warning: {len(unchecked)} equipment instances not in any chain:")
            for eq in unchecked:
                eq_id = getattr(eq, "equipmentId", eq.name)
                eq_class = getattr(eq.memberOfClass, "equipmentClassId", "Unknown") if getattr(eq, "memberOfClass", None) else "Unknown"
                print(f"    • {eq_id} (class: {eq_class})")

def trace_equipment_chain(onto, equipment, checked_instances, depth=0):
    """Recursively trace and print the equipment chain."""
    if equipment in checked_instances:
        return
        
    checked_instances.add(equipment)
    indent = "    " * depth
    eq_id = getattr(equipment, "equipmentId", equipment.name)
    eq_class = getattr(equipment.memberOfClass, "equipmentClassId", "Unknown") if getattr(equipment, "memberOfClass", None) else "Unknown"
    
    if depth == 0:
        print(f"  Chain starting with: {eq_id} (class: {eq_class})")
    else:
        print(f"{indent}→ {eq_id} (class: {eq_class})")
    
    # Follow the downstream connections
    downstream_equipment = getattr(equipment, "equipmentIsUpstreamOf", [])
    for downstream in downstream_equipment:
        trace_equipment_chain(onto, downstream, checked_instances, depth + 1)

def main():
    """Run the equipment chaining tests."""
    # Test the parse_equipment_class function
    test_parse_equipment_class()
    
    # Create test ontology
    onto = create_test_ontology()
    
    # Define test configurations
    # Each line has a list of equipment with name and ID
    # Use names that will test the class name parsing (with digits, etc.)
    line_configs = {
        # Line 1: Complete sequence with multiple instances of some types
        "LINE001": [
            {"name": "FIPCO009_Filler1", "id": "F001"},
            {"name": "FIPCO009_Filler2", "id": "F002"},
            {"name": "FIPCO009_Labeler", "id": "L001"},
            {"name": "FIPCO009_CaseFormer", "id": "CF001"},
            {"name": "FIPCO009_CaseSealer1", "id": "CS001"},
            {"name": "FIPCO009_CaseSealer2", "id": "CS002"}
        ],
        
        # Line 2: Missing middle equipment type (Labeler)
        "LINE002": [
            {"name": "FIPCO009_Filler1", "id": "F003"},
            {"name": "FIPCO009_CaseFormer", "id": "CF002"},
            {"name": "FIPCO009_CaseSealer", "id": "CS003"}
        ],
        
        # Line 3: Only one equipment type
        "LINE003": [
            {"name": "FIPCO009_Filler1", "id": "F004"},
            {"name": "FIPCO009_Filler2", "id": "F005"},
            {"name": "FIPCO009_Filler3", "id": "F006"}
        ]
    }
    
    # Create test data
    classes, properties, prop_is_functional, class_positions = create_test_equipment(onto, line_configs)
    
    # Run the equipment chaining function
    setup_equipment_instance_relationships(
        onto=onto,
        defined_classes=classes,
        defined_properties=properties,
        property_is_functional=prop_is_functional,
        equipment_class_positions=class_positions
    )
    
    # Verify the chains created
    verify_equipment_chains(onto)
    
    print("\nTest complete!")

if __name__ == "__main__":
    main() 