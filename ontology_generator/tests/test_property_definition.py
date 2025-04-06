"""
Tests for property definition functionality (TKT-001 fix).

This module tests the property definition functionality to ensure that
properties are correctly defined with all required attributes.
"""
import unittest
import sys
import os
from typing import Dict, List
from owlready2 import (
    World, Ontology, ThingClass, PropertyClass, Thing,
    ObjectProperty, DataProperty, FunctionalProperty
)

# Add src directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ontology_generator.definition.structure import define_ontology_structure


class TestPropertyDefinition(unittest.TestCase):
    """Test cases for property definition."""

    def setUp(self):
        """Set up test environment."""
        self.world = World()
        self.onto = self.world.get_ontology("http://test.org/onto.owl")
        
        # Initialize XSD type map for testing
        from ontology_generator.config import XSD_TYPE_MAP
        XSD_TYPE_MAP.update({
            "xsd:string": str,
            "xsd:integer": int,
            "xsd:float": float,
            "xsd:boolean": bool
        })
        
        # Create a minimal specification with both object and data properties
        self.specification: List[Dict[str, str]] = [
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

    def test_property_creation(self):
        """Test that properties are correctly created with required attributes."""
        # Define ontology structure
        defined_classes, defined_properties, property_is_functional = define_ontology_structure(
            self.onto, self.specification
        )
        
        # Verify classes were defined
        self.assertIn("TestClass", defined_classes)
        self.assertIn("RelatedClass", defined_classes)
        
        # Verify properties were defined
        self.assertIn("testObjectProperty", defined_properties)
        self.assertIn("testDataProperty", defined_properties)
        
        # Verify property types
        test_obj_prop = defined_properties["testObjectProperty"]
        test_data_prop = defined_properties["testDataProperty"]
        
        # TKT-001: There are different ways to check property types
        # Depending on owlready2's implementation
        self.assertTrue(issubclass(test_obj_prop, ObjectProperty) or 
                       isinstance(test_obj_prop, ObjectProperty))
        self.assertTrue(issubclass(test_data_prop, DataProperty) or
                       isinstance(test_data_prop, DataProperty))
        
        # TKT-001: Verify properties have necessary attributes
        # The main bug fixed in TKT-001 was properties lacking 'iri' attribute
        self.assertTrue(hasattr(test_obj_prop, "iri"))
        self.assertTrue(hasattr(test_data_prop, "iri"))
        
        # Check that IRIs are properly formed
        self.assertTrue(test_obj_prop.iri.endswith("#testObjectProperty"))
        self.assertTrue(test_data_prop.iri.endswith("#testDataProperty"))
        
        # Verify domain and range
        self.assertEqual(len(test_obj_prop.domain), 1)
        self.assertEqual(test_obj_prop.domain[0], defined_classes["TestClass"])
        
        self.assertEqual(len(test_obj_prop.range), 1)
        self.assertEqual(test_obj_prop.range[0], defined_classes["RelatedClass"])
        
        # Verify characteristics
        self.assertTrue(issubclass(test_obj_prop, FunctionalProperty) or
                       isinstance(test_obj_prop, FunctionalProperty))
        self.assertTrue(issubclass(test_data_prop, FunctionalProperty) or
                       isinstance(test_data_prop, FunctionalProperty))
        
        # Verify Python name is correctly set (needed for population)
        self.assertTrue(hasattr(test_obj_prop, "python_name"))
        self.assertTrue(hasattr(test_data_prop, "python_name"))
        self.assertEqual(test_obj_prop.python_name, "testObjectProperty")
        self.assertEqual(test_data_prop.python_name, "testDataProperty")


if __name__ == "__main__":
    unittest.main()

def test_property_definition():
    """Run property definition tests and return True if all pass."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPropertyDefinition)
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    
    return len(result.errors) == 0 and len(result.failures) == 0 