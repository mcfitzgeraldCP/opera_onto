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
    
    # Add descriptive label if available
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
        # elif pass_num == 1: # Mappings missing or wrong pass
        #     pop_logger.warning(f"No property mappings found for ProductionLine '{line_id}' or wrong pass ({pass_num}). Only basic individual created/retrieved.")
            # Ensure ID is set and link to process cell if possible (DEFER LINKING)
            # if not getattr(line_ind, "lineId", None):
            #     context.set_prop(line_ind, "lineId", line_id)
            # if pcell_ind and not getattr(line_ind, "locatedInProcessCell", None):
            #     pop_logger.warning(f"Manually linking Line '{line_id}' to ProcessCell '{pcell_id}' due to missing mapping.") # DEFER/REMOVE
            #     context.set_prop(line_ind, "locatedInProcessCell", pcell_ind) # DEFER/REMOVE

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
        # Error logged by get_class
        return None

    mat_id_map = property_mappings['Material'].get('data_properties', {}).get('materialId')
    if not mat_id_map or not mat_id_map.get('column'):
        pop_logger.warning("Cannot determine the column for Material.materialId from property mappings. Skipping material creation.")
        return None
    mat_id_col = mat_id_map['column']
    mat_id = safe_cast(row.get(mat_id_col), str)
    if not mat_id:
        pop_logger.debug(f"No Material ID found in column '{mat_id_col}', skipping material creation.")
        return None

    # Create descriptive labels for Material
    mat_labels = []
    
    # Try to get description for primary label
    mat_desc_map = property_mappings['Material'].get('data_properties', {}).get('materialDescription')
    mat_desc = None
    if mat_desc_map and mat_desc_map.get('column'):
        mat_desc = safe_cast(row.get(mat_desc_map['column']), str)
    
    # Primary label: Material description if available, otherwise ID
    if mat_desc:
        mat_labels.append(mat_desc)
    mat_labels.append(f"Material {mat_id}")
    
    # Always ensure the ID is in the labels
    if mat_id and f"ID:{mat_id}" not in mat_labels:
        mat_labels.append(f"ID:{mat_id}")

    # Create or retrieve Material individual using mat_id as the base identifier
    mat_ind = get_or_create_individual(cls_Material, mat_id, context.onto, all_created_individuals_by_uid, add_labels=mat_labels)
    if not mat_ind:
        pop_logger.error(f"Failed to create/retrieve Material individual for ID '{mat_id}'.")
        return None

    # Apply data properties in Pass 1
    if pass_num == 1:
        apply_data_property_mappings(mat_ind, property_mappings["Material"], row, context, "Material", pop_logger)

    return mat_ind


def process_production_request(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None, # Add registry
    pass_num: int = 1 # Add pass number
    ) -> Optional[Thing]:
    """
    Processes ProductionRequest from a row (Pass 1: Create/Data Props).

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
        pop_logger.warning("Property mappings for 'ProductionRequest' not provided or empty. Skipping request processing.")
        return None
    if all_created_individuals_by_uid is None:
         pop_logger.error("Individual registry not provided to process_production_request. Skipping.")
         return None

    cls_ProductionRequest = context.get_class("ProductionRequest")
    if not cls_ProductionRequest:
        # Error logged by get_class
        return None

    req_id_map = property_mappings['ProductionRequest'].get('data_properties', {}).get('requestId')
    if not req_id_map or not req_id_map.get('column'):
        pop_logger.warning("Cannot determine the column for ProductionRequest.requestId from property mappings. Skipping request creation.")
        return None
    req_id_col = req_id_map['column']

    req_id = safe_cast(row.get(req_id_col), str)
    if not req_id:
        pop_logger.debug(f"No Production Request ID in column '{req_id_col}', skipping request creation.")
        return None

    # Create descriptive labels for ProductionRequest
    req_labels = []
    
    # Try to get description for primary label
    req_desc_map = property_mappings['ProductionRequest'].get('data_properties', {}).get('requestDescription')
    req_desc = None
    if req_desc_map and req_desc_map.get('column'):
        req_desc = safe_cast(row.get(req_desc_map['column']), str)
    
    # Primary label: request description if available
    if req_desc:
        req_labels.append(req_desc)
    
    # Add request ID-based label
    req_labels.append(f"Production Request {req_id}")
    
    # Always ensure ID is in the labels
    if f"ID:{req_id}" not in req_labels:
        req_labels.append(f"ID:{req_id}")
    
    # Create or retrieve ProductionRequest individual using req_id as the base identifier
    req_ind = get_or_create_individual(cls_ProductionRequest, req_id, context.onto, all_created_individuals_by_uid, add_labels=req_labels)
    if not req_ind:
        pop_logger.error(f"Failed to create/retrieve ProductionRequest individual for ID '{req_id}'.")
        return None

    # Apply data properties in Pass 1
    if pass_num == 1:
        apply_data_property_mappings(req_ind, property_mappings["ProductionRequest"], row, context, "ProductionRequest", pop_logger)

    return req_ind
