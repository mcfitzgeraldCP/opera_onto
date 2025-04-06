"""
Unit tests for ontology_generator.population.core module.

This module tests the core population functionality including:
- PopulationContext
- get_or_create_individual
- _set_property_value
- apply_data_property_mappings
- apply_object_property_mappings
"""
import pytest
from unittest.mock import MagicMock, patch, call, ANY
import unittest.mock as mock
import logging
from typing import Dict, Tuple, List, Any, Optional
import pandas as pd

from owlready2 import (
    World, Ontology, ThingClass, PropertyClass, Thing,
    ObjectProperty, DataProperty, FunctionalProperty, 
    locstr, ObjectPropertyClass, DataPropertyClass
)

# Imports from ontology_generator
from ontology_generator.population.core import (
    PopulationContext, 
    get_or_create_individual,
    _set_property_value,
    apply_data_property_mappings,
    apply_object_property_mappings,
    IndividualRegistry,
    set_prop_if_col_exists
)

# Configure logging for tests
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_core")

# Type aliases for improved readability
IndividualRegistry = Dict[Tuple[str, str], Thing] # Key: (entity_type_str, unique_id_str), Value: Individual Object


@pytest.fixture
def mock_world():
    """Create a mock World for testing."""
    return World()


@pytest.fixture
def mock_onto(mock_world):
    """Create a mock Ontology for testing."""
    onto = mock_world.get_ontology("http://test.org/core-test")
    with onto:
        class TestClass(Thing):
            pass
        class SubTestClass(TestClass):
            pass
        class AnotherClass(Thing):
            pass
        class test_data_prop(DataProperty):
            domain = [TestClass]
            range = [str]
        class test_func_data_prop(DataProperty, FunctionalProperty):
            domain = [TestClass]
            range = [int]
        class test_obj_prop(ObjectProperty):
            domain = [TestClass]
            range = [AnotherClass]
        class test_func_obj_prop(ObjectProperty, FunctionalProperty):
            domain = [TestClass]
            range = [AnotherClass]
    return onto


@pytest.fixture
def mock_context(mock_onto, mocker):
    """Create a mock PopulationContext for testing."""
    defined_classes = {
        "TestClass": mock_onto.TestClass,
        "SubTestClass": mock_onto.SubTestClass,
        "AnotherClass": mock_onto.AnotherClass,
    }
    defined_properties = {
        "test_data_prop": mock_onto.test_data_prop,
        "test_func_data_prop": mock_onto.test_func_data_prop,
        "test_obj_prop": mock_onto.test_obj_prop,
        "test_func_obj_prop": mock_onto.test_func_obj_prop,
    }
    property_is_functional = {
        "test_data_prop": False,
        "test_func_data_prop": True,
        "test_obj_prop": False,
        "test_func_obj_prop": True,
    }
    
    # Create context without spy
    # mocker.spy(PopulationContext, 'set_prop')
    
    return PopulationContext(
        onto=mock_onto,
        defined_classes=defined_classes,
        defined_properties=defined_properties,
        property_is_functional=property_is_functional
    )


@pytest.fixture
def mock_registry():
    """Create a mock registry for testing."""
    return {}


class TestPopulationContext:
    """Tests for the PopulationContext class."""
    
    def test_init(self, mock_onto, mock_context):
        """Test PopulationContext initialization sets up state correctly."""
        # Check direct assignments
        assert mock_context.onto == mock_onto
        assert "TestClass" in mock_context.defined_classes
        assert "test_data_prop" in mock_context.defined_properties
        assert "test_func_data_prop" in mock_context.property_is_functional
        
        # Check cache initialization
        assert mock_context._property_cache == {}
        assert mock_context._class_cache == {}
        
        # Check counter initialization
        assert len(mock_context._property_access_count) == 4
        assert len(mock_context._property_usage_count) == 4
        assert all(count == 0 for count in mock_context._property_access_count.values())
        assert all(count == 0 for count in mock_context._property_usage_count.values())
        
        # Check other state initialization
        assert mock_context._property_misses == set()
        assert mock_context._individual_data_cache == {}

    def test_get_class(self, mock_context):
        """Test get_class returns correct classes and handles caching."""
        # Test retrieving an existing class
        cls = mock_context.get_class("TestClass")
        assert cls is not None
        assert cls.name == "TestClass"
        
        # Test caching works - should be added to cache
        assert "TestClass" in mock_context._class_cache
        
        # Test retrieval from cache (implicitly)
        cls_again = mock_context.get_class("TestClass")
        assert cls_again is cls  # Should be same instance
        
        # Test missing class
        missing_cls = mock_context.get_class("NonexistentClass")
        assert missing_cls is None

        # Test non-ThingClass object would return None
        mock_context.defined_classes["NotAClass"] = "string_value"
        not_a_class = mock_context.get_class("NotAClass")
        assert not_a_class is None

    def test_get_prop(self, mock_context):
        """Test get_prop returns correct properties, handles caching, and tracks access."""
        # Test retrieving an existing property
        prop = mock_context.get_prop("test_data_prop")
        assert prop is not None
        assert prop.name == "test_data_prop"
        
        # Test access count incremented
        assert mock_context._property_access_count["test_data_prop"] == 1
        
        # Test caching works - should be added to cache
        assert "test_data_prop" in mock_context._property_cache
        
        # Test retrieval from cache (implicitly)
        prop_again = mock_context.get_prop("test_data_prop")
        assert prop_again is prop  # Should be same instance
        assert mock_context._property_access_count["test_data_prop"] == 2  # Count should increase
        
        # Test missing property
        missing_prop = mock_context.get_prop("nonexistent_prop")
        assert missing_prop is None
        assert "nonexistent_prop" in mock_context._property_misses
        
        # Test non-PropertyClass object would return None
        mock_context.defined_properties["NotAProp"] = "string_value"
        not_a_prop = mock_context.get_prop("NotAProp")
        assert not_a_prop is None

    def test_set_prop(self, mock_context, mock_onto, mocker):
        """Test set_prop calls _set_property_value correctly."""
        # Create a test individual
        individual = mock_onto.TestClass("TestIndividual")
        
        # Mock _set_property_value to avoid side effects
        mock_set_prop = mocker.patch('ontology_generator.population.core._set_property_value')
        
        # Call set_prop
        mock_context.set_prop(individual, "test_data_prop", "test_value")
        
        # Verify _set_property_value was called with correct arguments
        mock_set_prop.assert_called_once_with(
            individual, 
            mock_context.get_prop("test_data_prop"), 
            "test_value", 
            False,  # is_functional 
            mock_context
        )
        
        # Test with nonexistent property - should not call _set_property_value
        mock_set_prop.reset_mock()
        mock_context.set_prop(individual, "nonexistent_prop", "value")
        mock_set_prop.assert_not_called()
        
        # Test with functional property
        mock_set_prop.reset_mock()
        mock_context.set_prop(individual, "test_func_data_prop", 42)
        mock_set_prop.assert_called_once_with(
            individual, 
            mock_context.get_prop("test_func_data_prop"), 
            42, 
            True,  # is_functional 
            mock_context
        )

    def test_store_individual_data(self, mock_context, mock_onto):
        """Test store_individual_data associates data with individuals."""
        # Create a test individual
        individual = mock_onto.TestClass("TestIndividual")
        
        # Test data to store
        test_data = {"col1": "value1", "col2": 42}
        
        # Store the data
        mock_context.store_individual_data(individual, test_data)
        
        # Verify data was stored
        assert individual.name in mock_context._individual_data_cache
        assert mock_context._individual_data_cache[individual.name] == test_data

    def test_get_individual_data(self, mock_context, mock_onto):
        """Test get_individual_data retrieves data associated with individuals."""
        # Create a test individual
        individual = mock_onto.TestClass("TestIndividual")
        
        # Test data to store
        test_data = {"col1": "value1", "col2": 42}
        
        # Store the data
        mock_context._individual_data_cache[individual.name] = test_data
        
        # Retrieve the data
        retrieved_data = mock_context.get_individual_data(individual)
        
        # Verify retrieved data matches stored data
        assert retrieved_data == test_data
        
        # Test retrieving data for an individual without stored data
        another_individual = mock_onto.TestClass("AnotherIndividual")
        assert mock_context.get_individual_data(another_individual) is None
        
        # Test retrieving with None or invalid individual
        assert mock_context.get_individual_data(None) is None
        assert mock_context.get_individual_data("not_an_individual") is None

    def test_report_property_usage(self, mock_context):
        """Test report_property_usage calculates usage statistics correctly."""
        # Simulate property access and usage
        mock_context._property_access_count["test_data_prop"] = 5
        mock_context._property_access_count["test_func_data_prop"] = 3
        mock_context._property_usage_count["test_data_prop"] = 2
        
        # Add a property miss
        mock_context._property_misses.add("missing_prop")
        
        # Generate report
        report = mock_context.report_property_usage()
        
        # Verify report contents
        assert report["total_properties"] == 4
        assert report["total_accessed"] == 2  # Only 2 properties were accessed
        assert report["total_used"] == 1  # Only 1 property was actually used
        
        # Check unused properties list includes all properties except test_data_prop
        assert "test_func_data_prop" in report["unused_properties"]
        assert "test_obj_prop" in report["unused_properties"]
        assert "test_func_obj_prop" in report["unused_properties"]
        assert "test_data_prop" not in report["unused_properties"]
        
        # Check accessed but unused contains test_func_data_prop
        assert "test_func_data_prop" in report["accessed_but_unused"]
        
        # Check most used
        assert len(report["most_used"]) == 1
        assert report["most_used"][0] == ("test_data_prop", 2)
        
        # Check property misses
        assert report["property_misses"] == ["missing_prop"]

    def test_log_property_usage_report(self, mock_context, mocker):
        """Test log_property_usage_report logs usage statistics appropriately."""
        # Mock the logger
        mock_logger = mocker.patch('ontology_generator.population.core.pop_logger')
        
        # Simulate property access and usage
        mock_context._property_access_count["test_data_prop"] = 5
        mock_context._property_usage_count["test_data_prop"] = 2
        mock_context._property_misses.add("missing_prop")
        
        # Call the method
        mock_context.log_property_usage_report()
        
        # Verify logger calls
        assert mock_logger.info.call_count >= 4  # At least 4 info calls
        assert mock_logger.warning.call_count >= 1  # At least 1 warning call
        
        # Check specific log messages
        mock_logger.info.assert_any_call("TKT-002: Property Usage Report")
        mock_logger.warning.assert_any_call(mock.ANY)  # Check for warning about undefined properties


@pytest.mark.parametrize(
    "onto_class, name_base, add_labels, expected_registry_key", [
        # Basic case - alphanumeric
        (lambda onto: onto.TestClass, "test123", None, ("TestClass", "test123")),
        # Case with spaces and special characters that need sanitizing
        (lambda onto: onto.TestClass, "Test Object #1", None, ("TestClass", "TestObject1")),
        # Case with labels
        (lambda onto: onto.TestClass, "test123", ["Label 1", "Label 2"], ("TestClass", "test123")),
    ]
)
def test_get_or_create_individual_new(mock_onto, mock_registry, onto_class, name_base, add_labels, expected_registry_key, mocker):
    """Test get_or_create_individual creates new individuals correctly."""
    # Mock sanitize_name to return a predictable value
    mocker.patch('ontology_generator.population.core.sanitize_name', side_effect=lambda x: x.replace(" ", "").replace("#", ""))
    
    # Run the function
    individual = get_or_create_individual(
        onto_class=onto_class(mock_onto),
        individual_name_base=name_base,
        onto=mock_onto,
        registry=mock_registry,
        add_labels=add_labels
    )
    
    # Verify individual was created
    assert individual is not None
    assert individual.name == f"{expected_registry_key[0]}_{expected_registry_key[1]}"
    
    # Verify registry entry
    assert expected_registry_key in mock_registry
    assert mock_registry[expected_registry_key] is individual
    
    # Verify labels were added if provided
    if add_labels:
        for label in add_labels:
            assert label in individual.label


def test_get_or_create_individual_existing_in_registry(mock_onto, mock_registry, mocker):
    """Test get_or_create_individual returns existing individuals from registry."""
    # Mock sanitize_name to return a predictable value
    mocker.patch('ontology_generator.population.core.sanitize_name', return_value="test123")
    
    # Create a pre-existing individual
    existing_individual = mock_onto.TestClass("TestClass_test123")
    
    # Add it to the registry
    registry_key = ("TestClass", "test123")
    mock_registry[registry_key] = existing_individual
    
    # Run the function - should return the existing individual
    individual = get_or_create_individual(
        onto_class=mock_onto.TestClass,
        individual_name_base="test123",
        onto=mock_onto,
        registry=mock_registry,
        add_labels=["New Label"]
    )
    
    # Verify the existing individual was returned
    assert individual is existing_individual
    
    # Verify labels were added
    assert "New Label" in individual.label


def test_get_or_create_individual_existing_in_onto(mock_onto, mock_registry, mocker):
    """Test get_or_create_individual finds individuals in ontology but not registry."""
    # Mock sanitize_name to return a predictable value
    mocker.patch('ontology_generator.population.core.sanitize_name', return_value="test123")
    
    # Create a pre-existing individual in the ontology but not in the registry
    with mock_onto:
        existing_individual = mock_onto.TestClass("TestClass_test123")
    
    # Mock search_one to return our existing individual
    mocker.patch.object(mock_onto, 'search_one', return_value=existing_individual)
    
    # Run the function - should find and return the existing individual
    individual = get_or_create_individual(
        onto_class=mock_onto.TestClass,
        individual_name_base="test123",
        onto=mock_onto,
        registry=mock_registry,
        add_labels=["New Label"]
    )
    
    # Verify the existing individual was returned
    assert individual is existing_individual
    
    # Verify it was added to the registry
    registry_key = ("TestClass", "test123")
    assert registry_key in mock_registry
    assert mock_registry[registry_key] is existing_individual
    
    # Verify labels were added
    assert "New Label" in individual.label


def test_get_or_create_individual_name_collision(mock_onto, mock_registry, mocker):
    """Test get_or_create_individual handles name collisions with different classes."""
    # Mock sanitize_name to return a predictable value
    mocker.patch('ontology_generator.population.core.sanitize_name', return_value="test123")
    
    # Create a pre-existing individual of a different class but with the same name
    with mock_onto:
        existing_individual = mock_onto.AnotherClass("TestClass_test123")
    
    # Mock search_one to return our existing individual
    mocker.patch.object(mock_onto, 'search_one', return_value=existing_individual)
    
    # Run the function - should fail due to name collision
    individual = get_or_create_individual(
        onto_class=mock_onto.TestClass,
        individual_name_base="test123",
        onto=mock_onto,
        registry=mock_registry,
        add_labels=["New Label"]
    )
    
    # Verify no individual was returned
    assert individual is None
    
    # Verify registry wasn't modified
    registry_key = ("TestClass", "test123")
    assert registry_key not in mock_registry


def test_get_or_create_individual_abstract_class(mock_onto, mock_registry, mocker):
    """Test get_or_create_individual handles abstract class correctly."""
    # Create a class that simulates ProductionLineOrEquipment
    with mock_onto:
        class ProductionLineOrEquipment(Thing):
            pass
    
    # Mock sanitize_name to return a predictable value
    mocker.patch('ontology_generator.population.core.sanitize_name', return_value="test123")
    
    # Run the function with ProductionLineOrEquipment
    individual = get_or_create_individual(
        onto_class=mock_onto.ProductionLineOrEquipment,
        individual_name_base="test123",
        onto=mock_onto,
        registry=mock_registry
    )
    
    # Verify no individual was created for this abstract class
    assert individual is None
    
    # Verify registry wasn't modified
    registry_key = ("ProductionLineOrEquipment", "test123")
    assert registry_key not in mock_registry


def test_set_property_value_functional(mock_onto, mocker):
    """Test _set_property_value for functional properties."""
    # Create test data
    individual = mock_onto.TestClass("TestIndividual")
    prop = mock_onto.test_func_data_prop
    
    # Mock context for tracking usage
    mock_context = MagicMock()
    mock_context._property_usage_count = {"test_func_data_prop": 0}
    
    # Test setting a value when none exists
    _set_property_value(individual, prop, 42, True, mock_context)
    assert individual.test_func_data_prop == 42
    assert mock_context._property_usage_count["test_func_data_prop"] == 1
    
    # Test setting same value again - should not increment usage
    mock_context._property_usage_count["test_func_data_prop"] = 0
    _set_property_value(individual, prop, 42, True, mock_context)
    assert individual.test_func_data_prop == 42
    assert mock_context._property_usage_count["test_func_data_prop"] == 0  # Unchanged
    
    # Test setting a different value - should increment usage
    _set_property_value(individual, prop, 43, True, mock_context)
    assert individual.test_func_data_prop == 43
    assert mock_context._property_usage_count["test_func_data_prop"] == 1
    
    # Test with None value - should not set or increment
    mock_context._property_usage_count["test_func_data_prop"] = 0
    _set_property_value(individual, prop, None, True, mock_context)
    assert individual.test_func_data_prop == 43  # Unchanged
    assert mock_context._property_usage_count["test_func_data_prop"] == 0


def test_set_property_value_non_functional(mock_onto, mocker):
    """Test _set_property_value for non-functional properties."""
    # Create test data
    individual = mock_onto.TestClass("TestIndividual")
    prop = mock_onto.test_data_prop
    
    # Mock context for tracking usage
    mock_context = MagicMock()
    mock_context._property_usage_count = {"test_data_prop": 0}
    
    # Test setting a value when none exists
    _set_property_value(individual, prop, "value1", False, mock_context)
    assert individual.test_data_prop == ["value1"]
    assert mock_context._property_usage_count["test_data_prop"] == 1
    
    # Test setting a different value - should append and increment
    _set_property_value(individual, prop, "value2", False, mock_context)
    assert individual.test_data_prop == ["value1", "value2"]
    assert mock_context._property_usage_count["test_data_prop"] == 2
    
    # Test setting same value again - should not append or increment
    mock_context._property_usage_count["test_data_prop"] = 0
    _set_property_value(individual, prop, "value1", False, mock_context)
    assert individual.test_data_prop == ["value1", "value2"]  # Unchanged
    assert mock_context._property_usage_count["test_data_prop"] == 0
    
    # Test with None value - should not set or increment
    _set_property_value(individual, prop, None, False, mock_context)
    assert individual.test_data_prop == ["value1", "value2"]  # Unchanged
    assert mock_context._property_usage_count["test_data_prop"] == 0


def test_apply_data_property_mappings(mock_onto, mock_context, mocker):
    """Test apply_data_property_mappings applies properties correctly."""
    # Create test individual
    individual = mock_onto.TestClass("TestIndividual")
    
    # Create test mappings
    mappings = {
        "data_properties": {
            "test_data_prop": {
                "column": "col_str",
                "data_type": "xsd:string"
            },
            "test_func_data_prop": {
                "column": "col_int",
                "data_type": "xsd:integer"
            },
            "missing_column_prop": {
                # No column specified - should be skipped
            },
            "missing_prop": {
                "column": "col_missing"
                # This property doesn't exist in the context
            },
            "empty_column_prop": {
                "column": "",  # Empty column value should trigger warning
                "data_type": "xsd:string"
            }
        }
    }
    
    # Create test row data
    row = {
        "col_str": "test value",
        "col_int": "42",  # String that needs casting
        # col_missing is intentionally missing
    }
    
    # Create a spy on set_prop to verify it's called
    set_prop_spy = mocker.patch.object(mock_context, 'set_prop')
    
    # Mock safe_cast to return values directly
    mocker.patch('ontology_generator.population.core.safe_cast', side_effect=lambda v, t: int(v) if t == int else v)
    
    # Create mock logger
    mock_logger = MagicMock()
    
    # Mock get_prop to return an actual property for missing_prop and empty_column_prop
    mock_context.get_prop = MagicMock(side_effect=lambda prop_name: 
        mock_onto.test_data_prop if prop_name in ["missing_prop", "empty_column_prop"] else
        mock_context.defined_properties.get(prop_name))
    
    # Call function
    apply_data_property_mappings(individual, mappings, row, mock_context, "TestEntity", mock_logger)
    
    # Verify set_prop was called correctly
    set_prop_spy.assert_any_call(individual, "test_data_prop", "test value")
    set_prop_spy.assert_any_call(individual, "test_func_data_prop", mock.ANY)
    
    # Verify logger was called for empty column value
    mock_logger.warning.assert_called()


def test_apply_object_property_mappings_column_lookup(mock_onto, mock_context, mocker):
    """Test apply_object_property_mappings with column-based linking."""
    # Create test individuals
    individual = mock_onto.TestClass("TestIndividual")
    target = mock_onto.AnotherClass("TargetIndividual")
    
    # Create test registry
    registry = {("AnotherClass", "target123"): target}
    
    # Create test mappings
    mappings = {
        "object_properties": {
            "test_obj_prop": {
                "target_class": "AnotherClass",
                "column": "target_id"
            }
        }
    }
    
    # Create test row data
    row = {"target_id": "target123"}
    
    # Create test row individuals dict
    row_individuals = {"TestClass": individual}
    
    # Mock safe_cast to return values directly
    mocker.patch('ontology_generator.population.core.safe_cast', side_effect=lambda v, t: v)
    
    # Create mock logger
    mock_logger = MagicMock()
    
    # Call function
    apply_object_property_mappings(
        individual, mappings, row, mock_context, "TestEntity", 
        mock_logger, registry, row_individuals
    )
    
    # Verify object property was set
    assert individual.test_obj_prop == [target]


def test_apply_object_property_mappings_context_lookup(mock_onto, mock_context, mocker):
    """Test apply_object_property_mappings with context-based linking."""
    # Create test individuals
    individual = mock_onto.TestClass("TestIndividual")
    target = mock_onto.AnotherClass("TargetIndividual")
    
    # Create test mappings
    mappings = {
        "object_properties": {
            "test_obj_prop": {
                "target_class": "AnotherClass",
                "target_link_context": "AnotherClass"
            }
        }
    }
    
    # Create test row data
    row = {}
    
    # Create test registry
    registry = {}
    
    # Create test row individuals dict with the target
    row_individuals = {
        "TestClass": individual,
        "AnotherClass": target
    }
    
    # Create mock logger
    mock_logger = MagicMock()
    
    # Call function
    apply_object_property_mappings(
        individual, mappings, row, mock_context, "TestEntity", 
        mock_logger, registry, row_individuals
    )
    
    # Verify object property was set
    assert individual.test_obj_prop == [target]


def test_set_prop_if_col_exists(mock_onto, mock_context, mocker):
    """Test set_prop_if_col_exists handles column existence and value casting."""
    # Create test individual
    individual = mock_onto.TestClass("TestIndividual")
    
    # Create mock logger
    mock_logger = MagicMock()
    
    # Mock safe_cast for testing
    mock_cast = mocker.patch('ontology_generator.population.core.safe_cast')
    mock_cast.return_value = 42
    
    # Create a spy on set_prop to verify it's called
    set_prop_spy = mocker.patch.object(mock_context, 'set_prop')
    
    # Test with existing column and valid value
    row = {"test_col": "42"}
    result = set_prop_if_col_exists(
        mock_context, individual, "test_func_data_prop", "test_col", 
        row, mock_cast, int, mock_logger
    )
    
    assert result is True
    
    # Verify context.set_prop was called with correct arguments
    set_prop_spy.assert_called_once_with(individual, "test_func_data_prop", 42) 