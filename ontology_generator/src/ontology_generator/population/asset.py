"""
Asset population module for the ontology generator.

This module provides functions for processing asset hierarchy data.
"""
from typing import Dict, Any, Optional, Tuple

from owlready2 import Thing

from ontology_generator.utils.logging import pop_logger
from ontology_generator.utils.types import safe_cast
from ontology_generator.population.core import (
    PopulationContext, get_or_create_individual, apply_data_property_mappings
)

# Type Alias for registry
IndividualRegistry = Dict[Tuple[str, str], Thing] # Key: (entity_type_str, unique_id_str), Value: Individual Object

def process_asset_hierarchy(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None, # Add registry
    pass_num: int = 1 # Add pass number
) -> Tuple[Optional[Thing], Optional[Thing], Optional[Thing], Optional[Thing]]:
    """
    Processes the asset hierarchy (Plant, Area, ProcessCell, ProductionLine)
    from a single data row for a specific population pass.

    Pass 1: Creates individuals, applies data properties, adds to registry.
    Pass 2: (Currently not handled here, linking done by apply_object_property_mappings)

    Args:
        row: The data row.
        context: Population context.
        property_mappings: Property mappings dictionary.
        all_created_individuals_by_uid: The central registry of individuals.
        pass_num: The current population pass (1 or 2).

    Returns:
        A tuple containing the Plant, Area, ProcessCell, and ProductionLine
        individuals created or retrieved for this row.
    """
    if not property_mappings:
        pop_logger.warning("Property mappings not provided to process_asset_hierarchy. Skipping.")
        return None, None, None, None
    if all_created_individuals_by_uid is None:
         pop_logger.error("Individual registry not provided to process_asset_hierarchy. Skipping.")
         return None, None, None, None

    # Get classes from context
    cls_Plant = context.get_class("Plant")
    cls_Area = context.get_class("Area")
    cls_ProcessCell = context.get_class("ProcessCell")
    cls_ProductionLine = context.get_class("ProductionLine")

    if not all([cls_Plant, cls_Area, cls_ProcessCell, cls_ProductionLine]):
        pop_logger.error("One or more essential asset classes (Plant, Area, ProcessCell, ProductionLine) not found. Cannot process hierarchy.")
        return None, None, None, None

    plant_ind: Optional[Thing] = None
    area_ind: Optional[Thing] = None
    pcell_ind: Optional[Thing] = None
    line_ind: Optional[Thing] = None

    # --- Plant ---
    # Check for plantId property mapping
    plant_id_map = property_mappings.get('Plant', {}).get('data_properties', {}).get('plantId')
    if not plant_id_map or not plant_id_map.get('column'):
        pop_logger.error("Cannot determine the column for Plant.plantId from property mappings. Skipping Plant creation.")
        return None, None, None, None
    plant_id_col = plant_id_map['column']
    plant_id = safe_cast(row.get(plant_id_col), str)
    if not plant_id:
        pop_logger.error(f"Missing or invalid Plant ID in column '{plant_id_col}'. Skipping Plant creation.")
        return None, None, None, None  # Plant is essential

    # Create descriptive labels for Plant
    plant_labels = []
    
    # Primary label: Plant ID (required)
    plant_labels.append(plant_id)
    
    # Add descriptive label if available - with property existence check
    plant_name_map = property_mappings.get('Plant', {}).get('data_properties', {}).get('plantName')
    if plant_name_map and plant_name_map.get('column'):
        plant_name = safe_cast(row.get(plant_name_map.get('column')), str)
        if plant_name and plant_name != plant_id:
            plant_labels.append(f"{plant_name}")
    
    # Create or retrieve Plant individual using plant_id as the base identifier
    plant_ind = get_or_create_individual(cls_Plant, plant_id, context.onto, all_created_individuals_by_uid, add_labels=plant_labels)

    if plant_ind and pass_num == 1 and "Plant" in property_mappings:
        apply_data_property_mappings(plant_ind, property_mappings["Plant"], row, context, "Plant", pop_logger)
    elif not plant_ind:
         pop_logger.error(f"Failed to create/retrieve Plant individual for ID '{plant_id}'. Cannot proceed with hierarchy.")
         return None, None, None, None

    # --- Area ---
    # Check for areaId property mapping
    area_id_map = property_mappings.get('Area', {}).get('data_properties', {}).get('areaId')
    if not area_id_map or not area_id_map.get('column'):
        pop_logger.warning("Cannot determine the column for Area.areaId from property mappings. Skipping Area/ProcessCell/Line creation.")
        return plant_ind, None, None, None
    area_id_col = area_id_map['column']

    raw_area_id = row.get(area_id_col)
    if not raw_area_id:
        pop_logger.warning(f"Missing or invalid Area ID in column '{area_id_col}'. Skipping Area/ProcessCell/Line creation.")
        return plant_ind, None, None, None
    area_id = safe_cast(raw_area_id, str)

    # Create descriptive labels for Area
    area_labels = []
    
    # Primary label: Area ID (required)
    area_labels.append(area_id)
    
    # Add descriptive label with hierarchy information
    if plant_id:
        area_labels.append(f"Area {area_id} in Plant {plant_id}")
    
    # Create or retrieve Area individual using area_id as the base identifier
    area_ind = get_or_create_individual(cls_Area, area_id, context.onto, all_created_individuals_by_uid, add_labels=area_labels)

    if area_ind and pass_num == 1 and "Area" in property_mappings:
        # Linking to Plant (locatedInPlant) happens in Pass 2 via apply_object_property_mappings
        apply_data_property_mappings(area_ind, property_mappings["Area"], row, context, "Area", pop_logger)
    elif not area_ind:
         pop_logger.warning(f"Failed to create/retrieve Area individual for ID '{area_id}'. Skipping ProcessCell/Line creation.")
         # Return what we have so far
         return plant_ind, None, None, None

    # --- ProcessCell ---
    # Check for processCellId property mapping
    pcell_id_map = property_mappings.get('ProcessCell', {}).get('data_properties', {}).get('processCellId')
    if not pcell_id_map or not pcell_id_map.get('column'):
        pop_logger.warning("Cannot determine the column for ProcessCell.processCellId from property mappings. Skipping ProcessCell/Line creation.")
        return plant_ind, area_ind, None, None
    pcell_id_col = pcell_id_map['column']

    pcell_id = safe_cast(row.get(pcell_id_col), str)
    if not pcell_id:
        pop_logger.warning(f"Missing or invalid ProcessCell ID in column '{pcell_id_col}'. Skipping ProcessCell/Line creation.")
        return plant_ind, area_ind, None, None

    # Create descriptive labels for ProcessCell
    pcell_labels = []
    
    # Primary label: ProcessCell ID (required)
    pcell_labels.append(pcell_id)
    
    # Add descriptive label with hierarchy information
    if plant_id and area_id:
        pcell_labels.append(f"Process Cell {pcell_id} in Area {area_id}, Plant {plant_id}")
    elif area_id:
        pcell_labels.append(f"Process Cell {pcell_id} in Area {area_id}")
    
    # Create or retrieve ProcessCell individual using pcell_id as the base identifier
    pcell_ind = get_or_create_individual(cls_ProcessCell, pcell_id, context.onto, all_created_individuals_by_uid, add_labels=pcell_labels)

    if pcell_ind and pass_num == 1 and "ProcessCell" in property_mappings:
        # Linking to Area (partOfArea) happens in Pass 2
        apply_data_property_mappings(pcell_ind, property_mappings["ProcessCell"], row, context, "ProcessCell", pop_logger)
    elif not pcell_ind:
        pop_logger.warning(f"Failed to create/retrieve ProcessCell individual for ID '{pcell_id}'. Skipping Line creation.")
        return plant_ind, area_ind, None, None

    # --- ProductionLine ---
    # Check for lineId property mapping
    line_id_map = property_mappings.get('ProductionLine', {}).get('data_properties', {}).get('lineId')
    if not line_id_map or not line_id_map.get('column'):
        pop_logger.warning("Cannot determine the column for ProductionLine.lineId from property mappings. Skipping Line creation.")
        return plant_ind, area_ind, pcell_ind, None
    line_id_col = line_id_map['column']

    raw_line_id = row.get(line_id_col)
    if not raw_line_id:
        pop_logger.warning(f"Missing or invalid Line ID in column '{line_id_col}'. Skipping Line creation.")
        return plant_ind, area_ind, pcell_ind, None # Return created individuals up to this point
    else:
        line_id = safe_cast(raw_line_id, str)
        
        # Use the line_id directly as the unique identifier for ProductionLine
        # This follows the naming convention: #ProductionLine_{LINE_NAME}
        line_unique_base = line_id
        
        # Create descriptive labels for the ProductionLine
        line_labels = []
        
        # Primary label: Line ID (required)
        line_labels.append(line_id)
        
        # Add a more descriptive label if we have plant/area information
        if plant_id and area_id and pcell_id:
            descriptive_label = f"Production Line {line_id} in {pcell_id}, {area_id}, {plant_id}"
            line_labels.append(descriptive_label)
        elif plant_id and pcell_id:
            descriptive_label = f"Production Line {line_id} in {pcell_id}, {plant_id}"
            line_labels.append(descriptive_label)
        
        # Create or retrieve the ProductionLine individual
        line_ind = get_or_create_individual(cls_ProductionLine, line_unique_base, context.onto, all_created_individuals_by_uid, add_labels=line_labels)

        if line_ind and pass_num == 1 and "ProductionLine" in property_mappings:
            # Linking to ProcessCell (locatedInProcessCell) happens in Pass 2
            apply_data_property_mappings(line_ind, property_mappings["ProductionLine"], row, context, "ProductionLine", pop_logger)
        elif not line_ind:
             pop_logger.warning(f"Failed to create/retrieve ProductionLine individual for base '{line_unique_base}'.")
             # Return what we have (line_ind will be None)
             return plant_ind, area_ind, pcell_ind, None

    # Return all individuals created/retrieved in this hierarchy for this row
    return plant_ind, area_ind, pcell_ind, line_ind


def process_material(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None, # Add registry
    pass_num: int = 1 # Add pass number
    ) -> Optional[Thing]:
    """
    Processes Material from a row using property mappings (Pass 1: Create/Data Props).

    Args:
        row: The data row
        context: The population context
        property_mappings: Property mappings dictionary
        all_created_individuals_by_uid: Central individual registry.
        pass_num: Current pass number.

    Returns:
        The Material individual or None
    """
    if not property_mappings or "Material" not in property_mappings:
        pop_logger.warning("Property mappings for 'Material' not provided or empty. Skipping material processing.")
        return None
    if all_created_individuals_by_uid is None:
         pop_logger.error("Individual registry not provided to process_material. Skipping.")
         return None

    cls_Material = context.get_class("Material")
    if not cls_Material:
        pop_logger.error("Material class not found in ontology. Skipping material processing.")
        return None

    # Check for materialId property mapping
    material_id_map = property_mappings["Material"].get("data_properties", {}).get("materialId")
    if not material_id_map or not material_id_map.get("column"):
        pop_logger.warning("Required property mapping 'materialId' not found. Skipping material creation.")
        return None

    material_id_col = material_id_map["column"]
    material_id = safe_cast(row.get(material_id_col), str)
    if not material_id:
        pop_logger.warning(f"Missing or invalid Material ID in column '{material_id_col}'. Skipping material creation.")
        return None

    # Create descriptive labels for Material
    material_labels = []
    
    # Primary label: Material ID (required)
    material_labels.append(material_id)
    
    # Add descriptive name label if available - with property existence check
    material_name_map = property_mappings["Material"].get("data_properties", {}).get("materialName")
    if material_name_map and material_name_map.get("column"):
        material_name_col = material_name_map["column"]
        material_name = safe_cast(row.get(material_name_col), str)
        if material_name and material_name != material_id:
            material_labels.append(f"{material_name}")
    
    # Create or retrieve Material individual using material_id as the base identifier
    material_ind = get_or_create_individual(cls_Material, material_id, context.onto, all_created_individuals_by_uid, add_labels=material_labels)

    if material_ind and pass_num == 1:
        apply_data_property_mappings(material_ind, property_mappings["Material"], row, context, "Material", pop_logger)
    
    return material_ind


def process_production_request(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None, # Add registry
    pass_num: int = 1 # Add pass number
    ) -> Optional[Thing]:
    """
    Processes ProductionRequest from a row using property mappings (Pass 1: Create/Data Props).

    Args:
        row: The data row
        context: The population context
        property_mappings: Property mappings dictionary
        all_created_individuals_by_uid: Central individual registry.
        pass_num: Current pass number.

    Returns:
        The ProductionRequest individual or None
    """
    if not property_mappings or "ProductionRequest" not in property_mappings:
        pop_logger.debug("Property mappings for 'ProductionRequest' not provided. Skipping request processing.")
        return None
    if all_created_individuals_by_uid is None:
        pop_logger.error("Individual registry not provided to process_production_request. Skipping.")
        return None

    cls_Request = context.get_class("ProductionRequest")
    if not cls_Request:
        pop_logger.error("ProductionRequest class not found in ontology. Skipping request processing.")
        return None

    # Check for requestId property mapping - critical for creating the request
    request_id_map = property_mappings["ProductionRequest"].get("data_properties", {}).get("requestId")
    if not request_id_map or not request_id_map.get("column"):
        pop_logger.warning("Required property mapping 'requestId' not found. Skipping production request creation.")
        return None

    request_id_col = request_id_map["column"]
    request_id = safe_cast(row.get(request_id_col), str)
    if not request_id:
        pop_logger.debug(f"Missing or invalid Request ID in column '{request_id_col}'. Skipping request creation.")
        return None

    # Check for batch property mapping - may be optional but useful for identification
    batch_id_map = property_mappings["ProductionRequest"].get("data_properties", {}).get("batchId")
    batch_id = None
    if batch_id_map and batch_id_map.get("column"):
        batch_id_col = batch_id_map["column"]
        batch_id = safe_cast(row.get(batch_id_col), str)

    # Create a unique base name, potentially incorporating batch ID
    request_unique_base = request_id
    if batch_id:
        request_unique_base = f"{request_id}_{batch_id}"

    # Create descriptive labels for request
    request_labels = []
    
    # Primary label: Request ID (required)
    if batch_id:
        request_labels.append(f"Request {request_id} (Batch {batch_id})")
    else:
        request_labels.append(f"Request {request_id}")
    
    # Create or retrieve the individual
    request_ind = get_or_create_individual(cls_Request, request_unique_base, context.onto, all_created_individuals_by_uid, add_labels=request_labels)

    if request_ind and pass_num == 1:
        apply_data_property_mappings(request_ind, property_mappings["ProductionRequest"], row, context, "ProductionRequest", pop_logger)
    
    return request_ind
