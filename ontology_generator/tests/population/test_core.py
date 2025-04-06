"""
Tests for Individual Registry Synchronization functionality.

This module tests the synchronization mechanism that ensures individuals
are correctly registered across passes during ontology population.
"""
import pytest
import logging
from typing import Dict, Tuple, List, Any
from owlready2 import (
    World, Ontology, ThingClass, PropertyClass, Thing,
    ObjectProperty, DataProperty, FunctionalProperty
)

# Imports from ontology_generator
from ontology_generator.population.core import PopulationContext
from ontology_generator.population.row_processor import (
    get_or_create_individual
)
from ontology_generator.utils.types import sanitize_name

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_registry_sync")


def test_registry_synchronization():
    """
    Test the registry synchronization mechanism of get_or_create_individual.
    
    Verifies that individuals created outside the registry are properly
    synchronized when later accessed via get_or_create_individual.
    """
    logger.info("Starting registry synchronization test")
    
    # Create a new world and ontology for testing
    world = World()
    onto = world.get_ontology("http://test.org/registry-sync-test")
    
    # Create a class for testing
    with onto:
        class TestClass(Thing):
            pass
    
    # Initialize registry
    registry: Dict[Tuple[str, str], Thing] = {}
    
    # Test Case 1: Create individual directly in the ontology (outside the registry mechanism)
    logger.info("Test Case 1: Creating individual directly in the ontology (bypassing registry)")
    test_id = "Test123"
    sanitized_id = sanitize_name(test_id)
    individual_name = f"TestClass_{sanitized_id}"
    
    # Create the individual directly
    with onto:
        direct_individual = TestClass(individual_name)
        logger.info(f"Created individual directly: {direct_individual.name}")
    
    # Verify the individual exists in the ontology but not in the registry
    found_by_search = onto.search_one(iri=f"*{individual_name}")
    in_registry = any(k[1] == sanitized_id for k in registry.keys())
    
    logger.info(f"Individual exists in ontology: {found_by_search is not None}")
    logger.info(f"Individual exists in registry: {in_registry}")
    assert found_by_search is not None, "Individual should exist in ontology"
    assert not in_registry, "Individual should not exist in registry yet"
    
    # Test Case 2: Try to create the same individual using get_or_create_individual
    logger.info("Test Case 2: Attempting to get/create the same individual via get_or_create_individual")
    retrieved_individual = get_or_create_individual(
        onto_class=TestClass,
        individual_name_base=test_id,
        onto=onto,
        registry=registry,
        add_labels=["Test Label"]
    )
    
    # Verify the individual was found and added to the registry
    found_by_search_after = onto.search_one(iri=f"*{individual_name}")
    in_registry_after = any(k[1] == sanitized_id for k in registry.keys())
    registry_entry = next((v for k, v in registry.items() if k[1] == sanitized_id), None)
    
    logger.info(f"Individual exists in ontology after get_or_create: {found_by_search_after is not None}")
    logger.info(f"Individual exists in registry after get_or_create: {in_registry_after}")
    logger.info(f"Registry entry is the same as original individual: {registry_entry is direct_individual}")
    
    assert found_by_search_after is not None, "Individual should still exist in ontology"
    assert in_registry_after, "Individual should now exist in registry"
    assert registry_entry is direct_individual, "Registry should contain the original individual"
    assert retrieved_individual is direct_individual, "get_or_create_individual should return the original individual"
    
    # Test Case 3: Verify no duplicate was created (count individuals)
    individuals_of_class = list(onto.search(type=TestClass))
    logger.info(f"Total individuals of TestClass: {len(individuals_of_class)}")
    assert len(individuals_of_class) == 1, "There should be exactly one individual of TestClass"
    
    # Test Case 4: Check that labels were added as specified
    has_label = "Test Label" in retrieved_individual.label
    logger.info(f"Individual has added label: {has_label}")
    assert has_label, "The individual should have the label 'Test Label'"
    
    logger.info("Registry synchronization test completed successfully!") 