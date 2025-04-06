"""
Unit tests for the ontology specification parser module.

This module contains tests for functions in definition/parser.py, including 
parse_specification, parse_property_mappings, validate_property_mappings, and read_data.
"""
import pytest
from unittest.mock import patch, mock_open, MagicMock, call
from io import StringIO
import csv
from collections import defaultdict

from ontology_generator.definition.parser import (
    parse_specification,
    parse_property_mappings,
    validate_property_mappings,
    read_data
)

# Sample CSV content for testing
VALID_SPEC_CSV = """Logical Group,Raw Data Column Name,Proposed OWL Entity,Proposed OWL Property,OWL Property Type,Target/Range (xsd:) / Target Class,OWL Property Characteristics,Inverse Property,Domain,Property Restrictions,ISA-95 Concept,Parent Class,Target Link Context,Notes/Considerations,Programmatic
Asset Hierarchy,EQUIPMENT_ID,Equipment,equipmentId,DatatypeProperty,xsd:string,Functional,,Equipment,,Equipment ID,ProductionLine,Preferred ID for Equipment Individual,,
Asset Hierarchy,EQUIPMENT_NAME,Equipment,equipmentName,DatatypeProperty,xsd:string,-,,Equipment,,Equipment Description,ProductionLine,Consider rdfs:label,,
Asset Hierarchy,N/A,Equipment,isPartOfProductionLine,ObjectProperty,ProductionLine,-,hasEquipmentPart,Equipment,,Hierarchy Scope,owl:Thing,ProductionLine,Links Equipment to ProductionLine,
Material & Prod Order,MATERIAL_ID,Material,materialId,DatatypeProperty,xsd:string,Functional,,Material,,MaterialDefinition ID,owl:Thing,,,
Equipment Class,N/A,Equipment,memberOfClass,ObjectProperty,EquipmentClass,Functional,hasInstance,Equipment,,EquipmentClass Hierarchy,Equipment,EquipmentClass,,
Equipment Class,N/A,EquipmentClass,hasInstance,ObjectProperty,Equipment,-,memberOfClass,EquipmentClass,,EquipmentClass Hierarchy,owl:Thing,Equipment,Inverse of memberOfClass,TRUE
Performance Metrics,DOWNTIME,EventRecord,downtimeMinutes,DatatypeProperty,xsd:double,Functional,,EventRecord,,OperationsPerformance Parameter,EventRecord,,,
Performance Metrics,RUN_TIME,EventRecord,runTimeMinutes,DatatypeProperty,xsd:double,Functional,,EventRecord,,OperationsPerformance Parameter,EventRecord,,,
"""

EMPTY_SPEC_CSV = ""

MISSING_COLUMNS_SPEC_CSV = """Logical Group,Raw Data Column Name,Proposed OWL Entity,Proposed OWL Property
Asset Hierarchy,EQUIPMENT_ID,Equipment,equipmentId
"""

INVALID_SPEC_CSV = """Logical Group,Raw Data Column Name,Proposed OWL Entity,Proposed OWL Property,OWL Property Type
Asset Hierarchy,EQUIPMENT_ID,Equipment,equipmentId,InvalidType
"""

VALID_DATA_CSV = """LINE_NAME,EQUIPMENT_ID,EQUIPMENT_NAME,MATERIAL_ID,DOWNTIME,RUN_TIME
Line1,100,Filler_1,Mat001,10.5,8.2
Line1,101,Cartoner_1,Mat001,5.2,12.8
"""

@pytest.fixture
def mock_specification():
    """Fixture to provide a parsed specification list"""
    # Convert CSV string to list of dictionaries
    csv_file = StringIO(VALID_SPEC_CSV)
    reader = csv.DictReader(csv_file)
    return list(reader)

def test_parse_specification_valid():
    """Test parsing a valid specification file"""
    with patch('builtins.open', mock_open(read_data=VALID_SPEC_CSV)):
        result = parse_specification('mock_path.csv')
        
        # Check that we have the expected number of rows
        assert len(result) == 8
        
        # Check the content of the first row
        assert result[0]['Proposed OWL Entity'] == 'Equipment'
        assert result[0]['Proposed OWL Property'] == 'equipmentId'
        assert result[0]['OWL Property Type'] == 'DatatypeProperty'
        assert result[0]['Raw Data Column Name'] == 'EQUIPMENT_ID'

def test_parse_specification_empty():
    """Test parsing an empty specification file"""
    with patch('builtins.open', mock_open(read_data=EMPTY_SPEC_CSV)):
        result = parse_specification('mock_path.csv')
        assert result == []

def test_parse_specification_file_not_found():
    """Test handling of file not found error"""
    with patch('builtins.open', side_effect=FileNotFoundError()):
        with pytest.raises(FileNotFoundError):
            parse_specification('nonexistent_file.csv')

def test_parse_specification_exception():
    """Test handling of general exceptions during parsing"""
    with patch('builtins.open', side_effect=Exception("Mock error")):
        with pytest.raises(Exception):
            parse_specification('mock_path.csv')

def test_parse_property_mappings_valid(mock_specification):
    """Test parsing valid property mappings from specification"""
    # Add source file path to mimic how specifications are normally processed
    for row in mock_specification:
        row['_source_file_path_'] = 'mock_path.csv'
    
    # Mock open to return the CSV data when checking for additional columns
    with patch('builtins.open', mock_open(read_data=VALID_SPEC_CSV)):
        result = parse_property_mappings(mock_specification)
        
        # Verify structure and content
        assert 'Equipment' in result
        assert 'data_properties' in result['Equipment']
        assert 'object_properties' in result['Equipment']
        
        # Check data properties
        data_props = result['Equipment']['data_properties']
        assert 'equipmentId' in data_props
        assert data_props['equipmentId']['column'] == 'EQUIPMENT_ID'
        assert data_props['equipmentId']['data_type'] == 'xsd:string'
        assert data_props['equipmentId']['functional'] is True
        
        # Check object properties
        obj_props = result['Equipment']['object_properties']
        assert 'isPartOfProductionLine' in obj_props
        assert obj_props['isPartOfProductionLine']['target_class'] == 'ProductionLine'
        assert 'target_link_context' in obj_props['isPartOfProductionLine']
        assert obj_props['isPartOfProductionLine']['target_link_context'] == 'ProductionLine'
        
        # Check programmatic flag
        assert 'EquipmentClass' in result
        assert 'hasInstance' in result['EquipmentClass']['object_properties']
        assert result['EquipmentClass']['object_properties']['hasInstance']['programmatic'] is True

def test_parse_property_mappings_missing_columns(mock_specification):
    """Test parsing with missing optional columns"""
    # Remove the Target Link Context and Programmatic columns from rows
    for row in mock_specification:
        if 'Target Link Context' in row:
            del row['Target Link Context']
        if 'Programmatic' in row:
            del row['Programmatic']
    
    # Mock the fieldnames check to simulate missing columns
    with patch('builtins.open', side_effect=Exception("Mock error")):
        # Even if opening the file fails, we should get fieldnames from the first row
        result = parse_property_mappings(mock_specification)
        
        # Check that we still have results
        assert 'Equipment' in result
        assert 'isPartOfProductionLine' in result['Equipment']['object_properties']
        
        # Without target link context column, properties can still be parsed but might not validate later
        obj_prop = result['Equipment']['object_properties']['isPartOfProductionLine'] 
        assert 'target_link_context' not in obj_prop

def test_parse_property_mappings_missing_property_type():
    """Test parsing with rows missing property type"""
    # Create a spec with a row missing property type
    invalid_spec = [
        {
            'Proposed OWL Entity': 'Equipment',
            'Proposed OWL Property': 'invalidProp',
            'Raw Data Column Name': 'SOME_COLUMN',
            'OWL Property Type': '',  # Empty property type instead of missing
        }
    ]
    
    # We need at least one valid row to create the entity
    valid_row = {
        'Proposed OWL Entity': 'Equipment',
        'Proposed OWL Property': 'validProp',
        'Raw Data Column Name': 'VALID_COLUMN',
        'OWL Property Type': 'DatatypeProperty',
        'Target/Range (xsd:) / Target Class': 'xsd:string'
    }
    
    invalid_spec.append(valid_row)
    
    result = parse_property_mappings(invalid_spec)
    
    # The invalid row should be skipped but the entity should exist
    assert 'Equipment' in result
    assert 'invalidProp' not in result['Equipment'].get('data_properties', {})
    assert 'invalidProp' not in result['Equipment'].get('object_properties', {})
    assert 'validProp' in result['Equipment'].get('data_properties', {})

def test_validate_property_mappings_valid():
    """Test validation with valid property mappings"""
    # Create valid mappings
    valid_mappings = {
        'EventRecord': {
            'data_properties': {
                'downtimeMinutes': {
                    'column': 'DOWNTIME',
                    'data_type': 'xsd:double',
                    'functional': True
                },
                'runTimeMinutes': {
                    'column': 'RUN_TIME',
                    'data_type': 'xsd:double',
                    'functional': True
                },
                'goodProductionQuantity': {
                    'column': 'GOOD_QTY',
                    'data_type': 'xsd:integer',
                    'functional': True
                },
                'reportedDurationMinutes': {
                    'column': 'TOTAL_TIME',
                    'data_type': 'xsd:double',
                    'functional': True
                },
                'effectiveRuntimeMinutes': {
                    'column': 'EFFECTIVE_RUNTIME',
                    'data_type': 'xsd:double',
                    'functional': True
                },
                'rejectProductionQuantity': {
                    'column': 'REJECT_QTY',
                    'data_type': 'xsd:integer',
                    'functional': True
                },
                'allMaintenanceTimeMinutes': {
                    'column': 'ALL_MAINTENANCE',
                    'data_type': 'xsd:double',
                    'functional': True
                }
            },
            'object_properties': {
                'involvesResource': {
                    'column': 'RESOURCE_ID',
                    'target_class': 'Resource',
                    'functional': False
                }
            }
        },
        'Equipment': {
            'data_properties': {
                'equipmentId': {
                    'column': 'EQUIPMENT_ID',
                    'data_type': 'xsd:string',
                    'functional': True
                }
            },
            'object_properties': {
                'isPartOfProductionLine': {
                    'target_class': 'ProductionLine',
                    'target_link_context': 'ProductionLine',
                    'functional': True
                },
                'memberOfClass': {
                    'target_class': 'EquipmentClass',
                    'programmatic': True,
                    'functional': True
                }
            }
        }
    }
    
    result = validate_property_mappings(valid_mappings)
    
    # Validation should pass
    assert result is True

def test_validate_property_mappings_empty():
    """Test validation with empty mappings"""
    with patch('ontology_generator.utils.logging.logger.error') as mock_error:
        result = validate_property_mappings({})
        
        # Validation should fail for empty mappings
        assert result is False
        mock_error.assert_called()

def test_validate_property_mappings_missing_required_fields():
    """Test validation with missing required fields"""
    # Create mappings with missing required fields
    invalid_mappings = {
        'Equipment': {
            'data_properties': {
                'missingColumn': {
                    # Missing column
                    'data_type': 'xsd:string',
                    'functional': False,
                    'programmatic': False  # Not programmatic either
                }
            },
            'object_properties': {
                'missingTargetClass': {
                    'column': 'SOME_COL',
                    # Missing target_class
                    'functional': False
                },
                'missingLinkMethod': {
                    'target_class': 'SomeClass',
                    # Missing column, context, and programmatic flag
                    'functional': False
                }
            }
        }
    }
    
    with patch('ontology_generator.utils.logging.logger.warning') as mock_warning:
        result = validate_property_mappings(invalid_mappings)
        
        # Validation should fail
        assert result is False
        
        # Verify warnings were logged
        assert mock_warning.call_count > 0

def test_validate_property_mappings_missing_eventrecord():
    """Test validation with missing EventRecord entity"""
    mappings_without_eventrecord = {
        'Equipment': {
            'data_properties': {
                'equipmentId': {
                    'column': 'EQUIPMENT_ID',
                    'data_type': 'xsd:string',
                    'functional': True
                }
            },
            'object_properties': {}
        }
    }
    
    with patch('ontology_generator.utils.logging.logger.warning') as mock_warning:
        result = validate_property_mappings(mappings_without_eventrecord)
        
        # Validation should fail due to missing EventRecord
        assert result is False
        
        # Verify warning about missing EventRecord was logged
        mock_warning.assert_called()

def test_validate_property_mappings_eventrecord_wrong_types():
    """Test validation with EventRecord properties having wrong data types"""
    mappings_with_wrong_types = {
        'EventRecord': {
            'data_properties': {
                'downtimeMinutes': {
                    'column': 'DOWNTIME',
                    'data_type': 'xsd:string',  # Wrong type, should be xsd:double
                    'functional': True
                },
                'goodProductionQuantity': {
                    'column': 'GOOD_QTY',
                    'data_type': 'xsd:double',  # Wrong type, should be xsd:integer
                    'functional': True
                },
                # Add other required properties to avoid missing property warnings
                'runTimeMinutes': {
                    'column': 'RUN_TIME',
                    'data_type': 'xsd:double',
                    'functional': True
                },
                'effectiveRuntimeMinutes': {
                    'column': 'EFFECTIVE_RUNTIME',
                    'data_type': 'xsd:double',
                    'functional': True
                },
                'reportedDurationMinutes': {
                    'column': 'TOTAL_TIME',
                    'data_type': 'xsd:double',
                    'functional': True
                },
                'rejectProductionQuantity': {
                    'column': 'REJECT_QTY',
                    'data_type': 'xsd:integer',
                    'functional': True
                },
                'allMaintenanceTimeMinutes': {
                    'column': 'ALL_MAINTENANCE',
                    'data_type': 'xsd:double',
                    'functional': True
                }
            },
            'object_properties': {}
        }
    }
    
    with patch('ontology_generator.utils.logging.logger.warning') as mock_warning:
        result = validate_property_mappings(mappings_with_wrong_types)
        
        # Validation should still pass, but warnings should be logged
        assert result is True
        
        # Verify logging was called
        mock_warning.assert_called()

def test_read_data_valid():
    """Test reading a valid data file"""
    with patch('builtins.open', mock_open(read_data=VALID_DATA_CSV)):
        result = read_data('mock_data.csv')
        
        # Check that we have the expected number of rows
        assert len(result) == 2
        
        # Check the content
        assert result[0]['LINE_NAME'] == 'Line1'
        assert result[0]['EQUIPMENT_ID'] == '100'
        assert result[0]['EQUIPMENT_NAME'] == 'Filler_1'
        assert result[0]['DOWNTIME'] == '10.5'

def test_read_data_file_not_found():
    """Test handling of file not found error when reading data"""
    with patch('builtins.open', side_effect=FileNotFoundError()):
        with pytest.raises(FileNotFoundError):
            read_data('nonexistent_file.csv')

def test_read_data_exception():
    """Test handling of general exceptions during data reading"""
    with patch('builtins.open', side_effect=Exception("Mock error")):
        with pytest.raises(Exception):
            read_data('mock_data.csv') 