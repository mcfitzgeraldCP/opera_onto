"""
Specification parsing module for the ontology generator.

This module provides functions for parsing the ontology specification file.
"""
import csv
from collections import defaultdict
from typing import List, Dict, Any, Optional

from ontology_generator.utils.logging import logger
from ontology_generator.config import (
    SPEC_COL_ENTITY, SPEC_COL_PROPERTY, SPEC_COL_PROP_TYPE,
    SPEC_COL_RAW_DATA, SPEC_COL_TARGET_RANGE, SPEC_COL_PROP_CHARACTERISTICS,
    SPEC_COL_INVERSE_PROPERTY, SPEC_COL_DOMAIN, SPEC_COL_TARGET_LINK_CONTEXT,
    SPEC_COL_PROGRAMMATIC, SPEC_COL_NOTES
)

def parse_specification(spec_file_path: str) -> List[Dict[str, str]]:
    """
    Parses the ontology specification CSV file.
    
    Args:
        spec_file_path: Path to the specification CSV file
        
    Returns:
        A list of dictionaries representing the specification rows
    """
    logger.info(f"Parsing specification file: {spec_file_path}")
    spec_list: List[Dict[str, str]] = []
    try:
        with open(spec_file_path, mode='r', encoding='utf-8-sig') as infile:  # Use utf-8-sig to handle potential BOM
            reader = csv.DictReader(infile)
            # Basic check for expected columns (optional but recommended)
            # expected_cols = {'Proposed OWL Entity', 'Proposed OWL Property', 'Parent Class', ...}
            # if not expected_cols.issubset(reader.fieldnames):
            #     logger.warning(f"Specification file might be missing expected columns. Found: {reader.fieldnames}")
            spec_list = list(reader)
            logger.info(f"Successfully parsed {len(spec_list)} rows from specification.")
            return spec_list
    except FileNotFoundError:
        logger.error(f"Specification file not found: {spec_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error parsing specification file {spec_file_path}: {e}")
        raise
    return []  # Return empty list on error if not raising

def parse_property_mappings(specification: List[Dict[str, str]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Parses the ontology specification to extract property-to-column mappings.
    
    Args:
        specification: The parsed specification list of dictionaries
        
    Returns:
        A nested dictionary with the structure:
        {
            'EntityName': {
                'data_properties': {
                    'propertyName': {
                        'column': 'RAW_DATA_COLUMN',
                        'data_type': 'xsd:type',
                        'functional': True/False,
                        'programmatic': True/False
                    }
                },
                'object_properties': {
                    'propertyName': {
                        'column': 'RAW_DATA_COLUMN',
                        'target_class': 'TargetClassName',
                        'functional': True/False,
                        'programmatic': True/False
                    }
                }
            }
        }
    """
    logger.info("Parsing property mappings from specification")
    mappings = defaultdict(lambda: {'data_properties': {}, 'object_properties': {}})
    
    # Get fieldnames to check for the new optional column
    fieldnames = []
    try:
        with open(specification[0]['_source_file_path_'], mode='r', encoding='utf-8-sig') as infile: # Assuming spec is not empty and comes from a file
             reader = csv.DictReader(infile)
             fieldnames = reader.fieldnames or []
    except Exception:
        # Fallback: Check the first row keys if reading file fails or spec is not from file
        if specification:
             fieldnames = list(specification[0].keys())
             
    has_target_link_context_col = SPEC_COL_TARGET_LINK_CONTEXT in fieldnames
    if not has_target_link_context_col:
        logger.warning(f"Specification file does not contain the '{SPEC_COL_TARGET_LINK_CONTEXT}' column. Context-based object property links may not be parsed.")
        
    has_programmatic_col = SPEC_COL_PROGRAMMATIC in fieldnames
    if not has_programmatic_col:
        logger.warning(f"Specification file does not contain the '{SPEC_COL_PROGRAMMATIC}' column. Programmatically-populated properties may not validate correctly.")

    for row_num, row in enumerate(specification):
        entity = row.get(SPEC_COL_ENTITY, '').strip()
        property_name = row.get(SPEC_COL_PROPERTY, '').strip()
        property_type = row.get(SPEC_COL_PROP_TYPE, '').strip()
        raw_data_col = row.get(SPEC_COL_RAW_DATA, '').strip()
        
        # Add source file path if not already present (useful for validation/debugging)
        if '_source_file_path_' not in row and hasattr(specification, '_source_file_path_'): 
             row['_source_file_path_'] = specification._source_file_path_ # Propagate if available
             
        # Skip if any essential fields are missing
        if not entity or not property_name:
            continue
            
        # Skip if property type is missing or invalid
        if property_type not in ['DatatypeProperty', 'ObjectProperty']:
            logger.warning(f"Skipping row {row_num+1}: Invalid or missing OWL Property Type '{property_type}' for {entity}.{property_name}")
            continue
            
        # Raw data col is optional for object properties if target link context is provided
        raw_data_col_is_na = not raw_data_col or raw_data_col.upper() == 'N/A'
        
        # Determine if the property is functional
        is_functional = 'Functional' in row.get(SPEC_COL_PROP_CHARACTERISTICS, '')
        
        # Determine if the property is populated programmatically - Fix for None issue
        programmatic_value = row.get(SPEC_COL_PROGRAMMATIC, '')
        is_programmatic = False
        if programmatic_value is not None and str(programmatic_value).strip().lower() == 'true':
            is_programmatic = True
        
        # Process data properties
        if property_type == 'DatatypeProperty':
            data_type = row.get(SPEC_COL_TARGET_RANGE, '').strip()
            # Create mapping info dictionary
            map_info = {
                'data_type': data_type,
                'functional': is_functional,
                'programmatic': is_programmatic
            }
            # Conditionally add the 'column' key
            if not raw_data_col_is_na:
                map_info['column'] = raw_data_col
                logger.debug(f"Mapped {entity}.{property_name} (DatatypeProperty) to column '{raw_data_col}', type '{data_type}'")
            else:
                # Log definition without mapping
                logger.debug(f"Defined {entity}.{property_name} (DatatypeProperty) type '{data_type}' but no data column mapping.")
            
            # Add to mappings regardless of column presence
            mappings[entity]['data_properties'][property_name] = map_info
            
        # Process object properties
        elif property_type == 'ObjectProperty':
            target_class = row.get(SPEC_COL_TARGET_RANGE, '').strip()
            target_link_context = row.get(SPEC_COL_TARGET_LINK_CONTEXT, '').strip() if has_target_link_context_col else ''
            
            # Initialize mapping info
            map_info = {
                'target_class': target_class,
                'functional': is_functional,
                'programmatic': is_programmatic
            }

            # Check if there's a way to populate/link this property later
            can_populate = False
            if not raw_data_col_is_na:
                # Prefer column mapping if available
                map_info['column'] = raw_data_col
                can_populate = True
                logger.debug(f"Mapped {entity}.{property_name} (ObjectProperty) to column '{raw_data_col}', target '{target_class}'")
                # Warn if context is also provided but will be ignored
                if target_link_context:
                    logger.warning(f"Row {row_num+1}: Both '{SPEC_COL_RAW_DATA}' ('{raw_data_col}') and '{SPEC_COL_TARGET_LINK_CONTEXT}' ('{target_link_context}') provided for {entity}.{property_name}. Prioritizing column lookup.")
            elif target_link_context:
                # Use context mapping if column is not available
                map_info['target_link_context'] = target_link_context
                can_populate = True
                logger.debug(f"Mapped {entity}.{property_name} (ObjectProperty) via context '{target_link_context}', target '{target_class}'")
            elif is_programmatic:
                # Property is populated programmatically
                can_populate = True
                logger.debug(f"Defined {entity}.{property_name} (ObjectProperty) target '{target_class}' to be populated programmatically.")
            else:
                 # Defined but cannot be populated from data/context
                 logger.debug(f"Defined {entity}.{property_name} (ObjectProperty) target '{target_class}' but no column or context for mapping.")

            # Add to mappings regardless of populatability, including mapping info if available
            mappings[entity]['object_properties'][property_name] = map_info
    
    # Convert defaultdict to regular dict for return
    return {k: {'data_properties': dict(v['data_properties']), 
                'object_properties': dict(v['object_properties'])} 
            for k, v in mappings.items()}

def validate_property_mappings(property_mappings: Dict[str, Dict[str, Dict[str, Any]]]) -> bool:
    """
    Validates property mappings and logs information for debugging.
    
    Args:
        property_mappings: Property mapping dictionary from parse_property_mappings
        
    Returns:
        bool: True if validation passed, False otherwise
    """
    logger.info("Validating property mappings...")
    
    if not property_mappings:
        logger.error("Property mappings dictionary is empty!")
        return False
    
    validation_passed = True
    entity_count = 0
    data_prop_count = 0
    object_prop_count = 0
    
    # Log summary
    logger.info(f"Found mappings for {len(property_mappings)} entities")
    
    # Check each entity
    for entity_name, entity_props in sorted(property_mappings.items()):
        entity_count += 1
        data_properties = entity_props.get('data_properties', {})
        object_properties = entity_props.get('object_properties', {})
        
        # Count properties
        data_prop_count += len(data_properties)
        object_prop_count += len(object_properties)
        
        # Log entity details
        logger.info(f"Entity: {entity_name} - {len(data_properties)} data properties, {len(object_properties)} object properties")
        
        # Log data properties
        if data_properties:
            logger.debug(f"  Data Properties for {entity_name}:")
            for prop_name, details in sorted(data_properties.items()):
                column = details.get('column', 'MISSING_COLUMN')
                data_type = details.get('data_type', 'MISSING_TYPE')
                functional = details.get('functional', False)
                programmatic = details.get('programmatic', False)
                
                logger.debug(f"    {prop_name}: column='{column}', type='{data_type}', functional={functional}, programmatic={programmatic}")
                
                # Validate required fields
                if not column and not programmatic and not data_type:
                    logger.warning(f"Missing required field for {entity_name}.{prop_name}: column='{column}', type='{data_type}'")
                    validation_passed = False
        
        # Log object properties
        if object_properties:
            logger.debug(f"  Object Properties for {entity_name}:")
            for prop_name, details in sorted(object_properties.items()):
                column = details.get('column', None) # Changed default to None
                target = details.get('target_class', 'MISSING_TARGET')
                functional = details.get('functional', False)
                link_context = details.get('target_link_context', None) # Added context check
                programmatic = details.get('programmatic', False) # Check for programmatic flag

                log_msg = f"    {prop_name}: target='{target}', functional={functional}"
                if column:
                     log_msg += f", column='{column}'"
                if link_context:
                     log_msg += f", context='{link_context}'"
                if programmatic:
                     log_msg += f", programmatic=True"
                logger.debug(log_msg)
                
                # Validate required fields
                if not target:
                    logger.warning(f"Missing required field target_class for {entity_name}.{prop_name}")
                    validation_passed = False
                # Must have either column or context or be programmatic
                if not column and not link_context and not programmatic:
                    logger.warning(f"Missing required field: Needs 'column', 'target_link_context', or 'Programmatic=True' for {entity_name}.{prop_name}")
                    validation_passed = False
    
    # Check for EventRecord specifically
    if 'EventRecord' not in property_mappings:
        logger.warning("No mappings found for 'EventRecord' entity (the main focus of this change)")
        validation_passed = False
    else:
        # Check for common EventRecord properties
        event_props = property_mappings['EventRecord'].get('data_properties', {})
        # TKT-006: Expanded check for AE model metrics
        expected_props = [
            'downtimeMinutes', 
            'runTimeMinutes', 
            'effectiveRuntimeMinutes', 
            'reportedDurationMinutes',
            'goodProductionQuantity',
            'rejectProductionQuantity',
            'allMaintenanceTimeMinutes'
        ]
        missing_props = [p for p in expected_props if p not in event_props]
        
        if missing_props:
            logger.warning(f"Some expected EventRecord AE model properties are missing from mappings: {missing_props}")
            # Don't fail validation for this, but log the warning
        
        # TKT-006: Verify that xsd:double is used for time metrics and xsd:integer for quantities
        time_metrics = [
            'downtimeMinutes', 
            'runTimeMinutes', 
            'effectiveRuntimeMinutes', 
            'reportedDurationMinutes',
            'allMaintenanceTimeMinutes'
        ]
        quantity_metrics = [
            'goodProductionQuantity',
            'rejectProductionQuantity'
        ]
        
        for prop in time_metrics:
            if prop in event_props:
                data_type = event_props[prop].get('data_type')
                if data_type not in ['xsd:double', 'xsd:decimal', 'xsd:float']:
                    logger.warning(f"EventRecord time metric '{prop}' should use 'xsd:double' data type, found '{data_type}'")
        
        for prop in quantity_metrics:
            if prop in event_props:
                data_type = event_props[prop].get('data_type')
                if data_type not in ['xsd:integer', 'xsd:int']:
                    logger.warning(f"EventRecord quantity metric '{prop}' should use 'xsd:integer' data type, found '{data_type}'")

    # Log summary stats
    logger.info(f"Property mapping validation complete. Found {entity_count} entities, {data_prop_count} data properties, {object_prop_count} object properties.")
    logger.info(f"Validation {'PASSED' if validation_passed else 'FAILED'}")
    
    return validation_passed

def read_data(data_file_path: str) -> List[Dict[str, str]]:
    """
    Reads the operational data CSV file.
    
    Args:
        data_file_path: Path to the data CSV file
        
    Returns:
        A list of dictionaries representing the data rows
    """
    logger.info(f"Reading data file: {data_file_path}")
    data_rows: List[Dict[str, str]] = []
    try:
        with open(data_file_path, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            data_rows = list(reader)
            logger.info(f"Successfully read {len(data_rows)} data rows.")
            return data_rows
    except FileNotFoundError:
        logger.error(f"Data file not found: {data_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading data file {data_file_path}: {e}")
        raise
    return []  # Return empty list on error if not raising
