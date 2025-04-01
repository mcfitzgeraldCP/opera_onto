"""
Specification parsing module for the ontology generator.

This module provides functions for parsing the ontology specification file.
"""
import csv
from collections import defaultdict
from typing import List, Dict, Any, Optional

from ontology_generator.utils.logging import logger

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
                        'functional': True/False
                    }
                },
                'object_properties': {
                    'propertyName': {
                        'column': 'RAW_DATA_COLUMN',
                        'target_class': 'TargetClassName',
                        'functional': True/False
                    }
                }
            }
        }
    """
    logger.info("Parsing property mappings from specification")
    mappings = defaultdict(lambda: {'data_properties': {}, 'object_properties': {}})
    
    for row in specification:
        entity = row.get('Proposed OWL Entity', '').strip()
        property_name = row.get('Proposed OWL Property', '').strip()
        property_type = row.get('OWL Property Type', '').strip()
        raw_data_col = row.get('Raw Data Column Name', '').strip()
        
        # Skip if any essential fields are missing
        if not entity or not property_name:
            continue
            
        # Skip if no raw data column or explicitly N/A (defined in ontology but not mapped to data)
        if not raw_data_col or raw_data_col.upper() == 'N/A':
            continue
            
        # Determine if the property is functional
        is_functional = 'Functional' in row.get('OWL Property Characteristics', '')
        
        # Process data properties
        if property_type == 'DatatypeProperty':
            data_type = row.get('Target/Range (xsd:) / Target Class', '').strip()
            mappings[entity]['data_properties'][property_name] = {
                'column': raw_data_col,
                'data_type': data_type,
                'functional': is_functional
            }
            logger.debug(f"Mapped {entity}.{property_name} (DatatypeProperty) to column '{raw_data_col}', type '{data_type}'")
            
        # Process object properties
        elif property_type == 'ObjectProperty':
            target_class = row.get('Target/Range (xsd:) / Target Class', '').strip()
            # Only map if it's an object property with a raw data column (some might just be relationships)
            if raw_data_col:
                mappings[entity]['object_properties'][property_name] = {
                    'column': raw_data_col,
                    'target_class': target_class,
                    'functional': is_functional
                }
                logger.debug(f"Mapped {entity}.{property_name} (ObjectProperty) to column '{raw_data_col}', target '{target_class}'")
    
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
                
                logger.debug(f"    {prop_name}: column='{column}', type='{data_type}', functional={functional}")
                
                # Validate required fields
                if not column or not data_type:
                    logger.warning(f"Missing required field for {entity_name}.{prop_name}: column='{column}', type='{data_type}'")
                    validation_passed = False
        
        # Log object properties
        if object_properties:
            logger.debug(f"  Object Properties for {entity_name}:")
            for prop_name, details in sorted(object_properties.items()):
                column = details.get('column', 'MISSING_COLUMN')
                target = details.get('target_class', 'MISSING_TARGET')
                functional = details.get('functional', False)
                
                logger.debug(f"    {prop_name}: column='{column}', target='{target}', functional={functional}")
                
                # Validate required fields
                if not column or not target:
                    logger.warning(f"Missing required field for {entity_name}.{prop_name}: column='{column}', target='{target}'")
                    validation_passed = False
    
    # Check for EventRecord specifically
    if 'EventRecord' not in property_mappings:
        logger.warning("No mappings found for 'EventRecord' entity (the main focus of this change)")
        validation_passed = False
    else:
        # Check for common EventRecord properties
        event_props = property_mappings['EventRecord'].get('data_properties', {})
        expected_props = ['downtimeMinutes', 'runTimeMinutes', 'reportedDurationMinutes']
        missing_props = [p for p in expected_props if p not in event_props]
        
        if missing_props:
            logger.warning(f"Some expected EventRecord properties are missing from mappings: {missing_props}")
            # Don't fail validation for this, but log the warning
    
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
