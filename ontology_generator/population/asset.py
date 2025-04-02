"""
Asset population module for the ontology generator.

This module provides functions for processing asset hierarchy data.
"""
from typing import Dict, Any, Optional, Tuple

from owlready2 import Thing

from ontology_generator.utils.logging import pop_logger
from ontology_generator.utils.types import safe_cast
from ontology_generator.population.core import (
    PopulationContext, get_or_create_individual, apply_property_mappings,
    set_prop_if_col_exists
)

def process_asset_hierarchy(row: Dict[str, Any], 
                           context: PopulationContext, 
                           property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
                          ) -> Tuple[Optional[Thing], Optional[Thing], Optional[Thing], Optional[Thing]]:
    """
    Processes Plant, Area, ProcessCell, ProductionLine from a row.
    
    Args:
        row: The data row
        context: The population context
        property_mappings: Optional property mappings dictionary
        
    Returns:
        A tuple of plant, area, process cell, and production line individuals
    """
    # Get Classes
    cls_Plant = context.get_class("Plant")
    cls_Area = context.get_class("Area")
    cls_ProcessCell = context.get_class("ProcessCell")
    cls_ProductionLine = context.get_class("ProductionLine")
    if not all([cls_Plant, cls_Area, cls_ProcessCell, cls_ProductionLine]): 
        return None, None, None, None  # Abort if essential classes missing

    # Plant
    plant_id = safe_cast(row.get('PLANT'), str)
    if not plant_id:
        pop_logger.error("Missing PLANT ID in row.")
        return None, None, None, None  # Plant is essential for hierarchy
    plant_labels = [plant_id]
    plant_ind = get_or_create_individual(cls_Plant, plant_id, context.onto, add_labels=plant_labels)
    if plant_ind:
        # Check if we can use dynamic property mappings for Plant
        if property_mappings and "Plant" in property_mappings:
            plant_mappings = property_mappings["Plant"]
            apply_property_mappings(plant_ind, plant_mappings, row, context, "Plant")
        else:
            # Fallback to hardcoded property assignments
            context.set_prop(plant_ind, "plantId", plant_id)
    else: 
        return None, None, None, None  # Failed to create plant

    # Area
    raw_area_id = row.get('GH_FOCUSFACTORY')
    if not raw_area_id:
        pop_logger.error(f"Missing 'GH_FOCUSFACTORY' (Area ID) in row. Skipping Area/ProcessCell/Line creation for this row.")
        # Return the plant if it was created, but None for the rest of the hierarchy
        return plant_ind, None, None, None 
    area_id = safe_cast(raw_area_id, str) # Assign only if present

    area_unique_base = f"{plant_id}_{area_id}"
    area_labels = [area_id]
    area_ind = get_or_create_individual(cls_Area, area_unique_base, context.onto, add_labels=area_labels)
    if area_ind:
        # Check if we can use dynamic property mappings for Area
        if property_mappings and "Area" in property_mappings:
            area_mappings = property_mappings["Area"]
            apply_property_mappings(area_ind, area_mappings, row, context, "Area", pop_logger)
            # Also set the link to Plant (not in mappings)
            context.set_prop(area_ind, "locatedInPlant", plant_ind)
        else:
            # Fallback to hardcoded property assignments
            context.set_prop_if_col_exists(area_ind, "areaId", 'GH_FOCUSFACTORY', row, safe_cast, str, pop_logger)
            context.set_prop(area_ind, "locatedInPlant", plant_ind)  # Object Property
            
            # Added Area physical category name & category code to Area (Focus Factory)
            context.set_prop_if_col_exists(area_ind, "areaPhysicalCategoryName", 'PHYSICAL_AREA', row, safe_cast, str, pop_logger)
            context.set_prop_if_col_exists(area_ind, "areaCategoryCode", 'GH_CATEGORY', row, safe_cast, str, pop_logger)

    # ProcessCell (Corrected Source Column: GH_AREA)
    pcell_id = safe_cast(row.get('GH_AREA'), str) or "UnknownProcessCell"
    pcell_unique_base = f"{area_unique_base}_{pcell_id}"
    pcell_labels = [pcell_id]
    pcell_ind = get_or_create_individual(cls_ProcessCell, pcell_unique_base, context.onto, add_labels=pcell_labels)
    if pcell_ind:
        context.set_prop(pcell_ind, "processCellId", pcell_id)
        if area_ind:  # Link only if Area exists
            context.set_prop(pcell_ind, "partOfArea", area_ind)  # Object Property

    # ProductionLine
    raw_line_id = row.get('LINE_NAME')
    if not raw_line_id:
        pop_logger.error(f"Missing 'LINE_NAME' (Line ID) in row. Cannot create ProductionLine individual for this row.")
        line_ind = None # Allow continuing but log error
    else:
        line_id = safe_cast(raw_line_id, str)
        # Check if we can use dynamic property mappings for ProductionLine
        if property_mappings and "ProductionLine" in property_mappings:
            line_mappings = property_mappings["ProductionLine"]
            apply_property_mappings(line_ind, line_mappings, row, context, "ProductionLine", pop_logger)
            # Also set the link to ProcessCell (not in mappings)
            if pcell_ind:
                context.set_prop(line_ind, "locatedInProcessCell", pcell_ind) # Object Property
        else:
            # Fallback to hardcoded property assignments
            context.set_prop_if_col_exists(line_ind, "lineId", 'LINE_NAME', row, safe_cast, str, pop_logger)
            if pcell_ind:  # Link only if ProcessCell exists
                context.set_prop(line_ind, "locatedInProcessCell", pcell_ind)  # Object Property

    return plant_ind, area_ind, pcell_ind, line_ind


def process_material(row: Dict[str, Any], 
                    context: PopulationContext, 
                    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
                   ) -> Optional[Thing]:
    """
    Processes Material from a row.
    
    Args:
        row: The data row
        context: The population context
        property_mappings: Optional property mappings dictionary
        
    Returns:
        The Material individual or None
    """
    cls_Material = context.get_class("Material")
    if not cls_Material: 
        return None

    mat_id = safe_cast(row.get('MATERIAL_ID'), str)
    if not mat_id:
        pop_logger.debug("No MATERIAL_ID in row, skipping material creation.")
        return None

    mat_desc = safe_cast(row.get('SHORT_MATERIAL_ID'), str)
    mat_labels = [mat_id]
    if mat_desc: 
        mat_labels.append(mat_desc)

    mat_ind = get_or_create_individual(cls_Material, mat_id, context.onto, add_labels=mat_labels)
    if not mat_ind: 
        return None

    # Check if we can use dynamic property mappings
    if property_mappings and "Material" in property_mappings:
        material_mappings = property_mappings["Material"]
        apply_property_mappings(mat_ind, material_mappings, row, context, "Material", pop_logger)
    else:
        # Fallback to hardcoded property assignments
        pop_logger.debug(f"Using hardcoded property assignments for Material ID: {mat_id} (no dynamic mappings available)")
        # Set Material properties
        context.set_prop_if_col_exists(mat_ind, "materialId", 'MATERIAL_ID', row, safe_cast, str, pop_logger)
        context.set_prop_if_col_exists(mat_ind, "materialDescription", 'SHORT_MATERIAL_ID', row, safe_cast, str, pop_logger)
        context.set_prop_if_col_exists(mat_ind, "sizeType", 'SIZE_TYPE', row, safe_cast, str, pop_logger)
        context.set_prop_if_col_exists(mat_ind, "materialUOM", 'MATERIAL_UOM', row, safe_cast, str, pop_logger)
        # Combine UOM_ST and UOM_ST_SAP safely - requires slightly different check
        uom_st_val = None
        if 'UOM_ST' in row and row['UOM_ST']:
            uom_st_val = safe_cast(row['UOM_ST'], str)
        elif 'UOM_ST_SAP' in row and row['UOM_ST_SAP']:
            uom_st_val = safe_cast(row['UOM_ST_SAP'], str)
        else:
            pop_logger.error(f"Missing required column for Material.standardUOM (tried 'UOM_ST' and 'UOM_ST_SAP') in row: {context.row_to_string(row)}")
        if uom_st_val is not None:
            context.set_prop(mat_ind, "standardUOM", uom_st_val)
        context.set_prop_if_col_exists(mat_ind, "targetProductUOM", 'TP_UOM', row, safe_cast, str, pop_logger)
        context.set_prop_if_col_exists(mat_ind, "conversionFactor", 'PRIMARY_CONV_FACTOR', row, safe_cast, float, pop_logger)

    return mat_ind


def process_production_request(row: Dict[str, Any], 
                              context: PopulationContext, 
                              material_ind: Optional[Thing], 
                              property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
                             ) -> Optional[Thing]:
    """
    Processes ProductionRequest from a row.
    
    Args:
        row: The data row
        context: The population context
        material_ind: The associated material individual
        property_mappings: Optional property mappings dictionary
        
    Returns:
        The ProductionRequest individual or None
    """
    cls_ProductionRequest = context.get_class("ProductionRequest")
    if not cls_ProductionRequest: 
        return None

    req_id = safe_cast(row.get('PRODUCTION_ORDER_ID'), str)
    if not req_id:
        pop_logger.debug("No PRODUCTION_ORDER_ID in row, skipping production request creation.")
        return None

    req_desc = safe_cast(row.get('PRODUCTION_ORDER_DESC'), str)
    req_labels = [f"ID:{req_id}"]
    if req_desc: 
        req_labels.insert(0, req_desc)

    req_ind = get_or_create_individual(cls_ProductionRequest, req_id, context.onto, add_labels=req_labels)
    if not req_ind: 
        return None

    # Check if we can use dynamic property mappings
    if property_mappings and "ProductionRequest" in property_mappings:
        request_mappings = property_mappings["ProductionRequest"]
        apply_property_mappings(req_ind, request_mappings, row, context, "ProductionRequest", pop_logger)
    else:
        # Fallback to hardcoded property assignments
        pop_logger.debug(f"Using hardcoded property assignments for ProductionRequest ID: {req_id} (no dynamic mappings available)")
        # Set ProductionRequest properties
        context.set_prop_if_col_exists(req_ind, "requestId", 'PRODUCTION_ORDER_ID', row, safe_cast, str, pop_logger)
        context.set_prop_if_col_exists(req_ind, "requestDescription", 'PRODUCTION_ORDER_DESC', row, safe_cast, str, pop_logger)
        context.set_prop_if_col_exists(req_ind, "requestRate", 'PRODUCTION_ORDER_RATE', row, safe_cast, float, pop_logger)
        context.set_prop_if_col_exists(req_ind, "requestRateUOM", 'PRODUCTION_ORDER_UOM', row, safe_cast, str, pop_logger)

    # Note: Based on spec, no direct link from ProductionRequest to Material
    # The link is EventRecord -> ProductionRequest (associatedWithProductionRequest)
    # And EventRecord -> Material (usesMaterial).

    return req_ind
