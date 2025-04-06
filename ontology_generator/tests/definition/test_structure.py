"""
Tests for property definition functionality.

This module tests the property definition functionality to ensure that
properties are correctly defined with all required attributes.
"""
import pytest
from typing import Dict, List
from owlready2 import (
    World, Ontology, ThingClass, PropertyClass, Thing,
    ObjectProperty, DataProperty, FunctionalProperty
)

from ontology_generator.definition.structure import define_ontology_structure


@pytest.fixture
def test_env():
    """Set up test environment."""
    world = World()
    onto = world.get_ontology("http://test.org/onto.owl")
    
    # Initialize XSD type map for testing
    from ontology_generator.config import XSD_TYPE_MAP
    XSD_TYPE_MAP.update({
        "xsd:string": str,
        "xsd:integer": int,
        "xsd:float": float,
        "xsd:boolean": bool
    })
    
    # Create a minimal specification with both object and data properties
    specification: List[Dict[str, str]] = [
        {
            "Proposed OWL Entity": "TestClass",
            "Parent Class": "Thing"
        },
        {
            "Proposed OWL Entity": "RelatedClass",
            "Parent Class": "Thing"
        },
        {
            "Proposed OWL Property": "testObjectProperty",
            "OWL Property Type": "ObjectProperty",
            "Domain": "TestClass",
            "Target/Range (xsd:) / Target Class": "RelatedClass",
            "OWL Property Characteristics": "Functional",
            "Inverse Property": "",
            "Notes/Considerations": "Test object property"
        },
        {
            "Proposed OWL Property": "testDataProperty",
            "OWL Property Type": "DataProperty",
            "Domain": "TestClass",
            "Target/Range (xsd:) / Target Class": "xsd:string",
            "OWL Property Characteristics": "Functional",
            "Notes/Considerations": "Test data property"
        }
    ]
    
    return {"world": world, "onto": onto, "specification": specification}


def test_property_creation(test_env):
    """Test that properties are correctly created with required attributes."""
    onto = test_env["onto"]
    specification = test_env["specification"]
    
    # Define ontology structure
    defined_classes, defined_properties, property_is_functional = define_ontology_structure(
        onto, specification
    )
    
    # Verify classes were defined
    assert "TestClass" in defined_classes
    assert "RelatedClass" in defined_classes
    
    # Verify properties were defined
    assert "testObjectProperty" in defined_properties
    assert "testDataProperty" in defined_properties
    
    # Verify property types
    test_obj_prop = defined_properties["testObjectProperty"]
    test_data_prop = defined_properties["testDataProperty"]
    
    # TKT-001: There are different ways to check property types
    # Depending on owlready2's implementation
    assert (issubclass(test_obj_prop, ObjectProperty) or 
            isinstance(test_obj_prop, ObjectProperty))
    assert (issubclass(test_data_prop, DataProperty) or
            isinstance(test_data_prop, DataProperty))
    
    # TKT-001: Verify properties have necessary attributes
    # The main bug fixed in TKT-001 was properties lacking 'iri' attribute
    assert hasattr(test_obj_prop, "iri")
    assert hasattr(test_data_prop, "iri")
    
    # Check that IRIs are properly formed
    assert test_obj_prop.iri.endswith("#testObjectProperty")
    assert test_data_prop.iri.endswith("#testDataProperty")
    
    # Verify domain and range
    assert len(test_obj_prop.domain) == 1
    assert test_obj_prop.domain[0] == defined_classes["TestClass"]
    
    assert len(test_obj_prop.range) == 1
    assert test_obj_prop.range[0] == defined_classes["RelatedClass"]
    
    # Verify characteristics
    assert (issubclass(test_obj_prop, FunctionalProperty) or
            isinstance(test_obj_prop, FunctionalProperty))
    assert (issubclass(test_data_prop, FunctionalProperty) or
            isinstance(test_data_prop, FunctionalProperty))
    
    # Verify Python name is correctly set (needed for population)
    assert hasattr(test_obj_prop, "python_name")
    assert hasattr(test_data_prop, "python_name")
    assert test_obj_prop.python_name == "testObjectProperty"
    assert test_data_prop.python_name == "testDataProperty" 