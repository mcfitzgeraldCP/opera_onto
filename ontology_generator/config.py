"""
Ontology Generator Configuration

This module contains constants, mappings, and configuration settings for the ontology generator.
"""
from typing import Dict, Any, Type, Optional
from datetime import datetime, date, time
import logging

# --- General Configuration ---
DEFAULT_ONTOLOGY_IRI = "http://example.com/manufacturing_ontology.owl"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
SPEC_PARENT_CLASS_COLUMN = 'Parent Class'  # Assumed column name for hierarchy

# --- Warnings Suppression Configuration ---
# List of warning message substrings that should be suppressed in logs
SUPPRESSED_WARNINGS = [
    "Equipment.actualSequencePosition is missing 'column'",
    "EquipmentClass.defaultSequencePosition is missing 'column'",
    "No equipment instance relationships were created or verified",
    "Context entity 'EquipmentCapability' required for Equipment.hasCapability",
    "Context entity 'EventRecord' required for Material.materialUsedIn",
    "Context entity 'EventRecord' required for OperationalReason.reasonForEvent",
    "Context entity 'EventRecord' required for OperationalState.stateOfEvent",
    "Context entity 'EventRecord' required for ProductionRequest.hasAssociatedEvent",
    "Context entity 'EventRecord' required for Shift.includesEvent",
    "Context entity 'Person' required for EventRecord.performedBy",
    "Created new individual",
    "Context entity 'Material' required for EventRecord.consumedMaterial not found",
    "Context entity 'Material' required for EventRecord.producedMaterial not found",
    "Context entity 'ProductionRequest' required for EventRecord.associatedRequest not found",
    "Successfully linked EventRecord",
    "Successfully linking Equipment",
    "Linked (Start-Time Containment):"
]

# --- Log Filter Class ---
class MessageFilter(logging.Filter):
    """
    A logging filter that suppresses specific log messages at any level
    """
    def __init__(self, suppressed_messages):
        super().__init__()
        self.suppressed_messages = suppressed_messages
        
    def filter(self, record):
        # Return False to suppress the message
        for msg in self.suppressed_messages:
            if msg in record.getMessage():
                return False
        return True

def setup_logging_filters():
    """
    Set up logging filters for all configured levels.
    This should be called during initial setup.
    """
    # Create the message filter with our suppressed warnings
    message_filter = MessageFilter(SUPPRESSED_WARNINGS)
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Add the filter to the root logger
    root_logger.addFilter(message_filter)
    
    # Also add the filter directly to specific loggers that we know generate these messages
    pop_logger = logging.getLogger("ontology_generator.population")
    pop_logger.addFilter(message_filter)
    
    row_proc_logger = logging.getLogger("ontology_generator.population.row_processor")
    row_proc_logger.addFilter(message_filter)
    
    core_logger = logging.getLogger("ontology_generator.population.core")
    core_logger.addFilter(message_filter)
    
    # Add filter to event_linking logger
    event_linking_logger = logging.getLogger("event_linking")
    event_linking_logger.addFilter(message_filter)

# --- Language Mapping for Alternative Reason Descriptions ---
# Mapping from country descriptions to BCP 47 language tags
COUNTRY_TO_LANGUAGE: Dict[str, str] = {
    "Mexico": "es",
    "United States": "en",
    "Brazil": "pt",
    "France": "fr",
    "Germany": "de",
    "Italy": "it",
    "Spain": "es",
    "Japan": "ja",
    "China": "zh",
    # Add more mappings as needed based on your data
}
DEFAULT_LANGUAGE = "en"  # Default language if country not found in mapping


# --- Default Equipment Class Sequencing ---
# Defines a default linear sequence for common equipment types
# NOTE: This is a restricted list for safety during the proof of concept phase.
# TODO: In the future, this will be expanded to support additional equipment classes
# and potentially be loaded from an external configuration source.
DEFAULT_EQUIPMENT_SEQUENCE: Dict[str, int] = {
    # Standard equipment classes with their sequence positions
    "Filler": 1,
    "Cartoner": 2,
    "Bundler": 3,
    "CaseFormer": 4,
    "CasePacker": 5,
    "CaseSealer": 6,
    "Palletizer": 7
    # Add any other standard equipment classes with default positions as needed
}

# --- Line-Specific Equipment Sequencing ---
# Defines line-specific sequences that override the default sequence
# Each line ID maps to a dictionary of equipment classes with their sequence positions
LINE_SPECIFIC_EQUIPMENT_SEQUENCE: Dict[str, Dict[str, int]] = {
    # Example for filling line
    "Line1": {
        "Unscrambler": 1,
        "RinseDryInvert": 2,
        "BottleInspector": 3,
        "Filler": 4,
        "Capper": 5,
        "Labeler": 6
    },
    # Example for packaging line
    "Line2": {
        "Cartoner": 1,
        "Bundler": 2,
        "CaseFormer": 3,
        "CasePacker": 4,
        "CaseSealer": 5,
        "Palletizer": 6
    },
    # Add line-specific sequences as needed
}

# --- XSD Type Mapping ---
# This will be initialized when importing the required modules to avoid
# circular imports with owlready2 types
XSD_TYPE_MAP: Dict[str, Type] = {}

def init_xsd_type_map(locstr_type: Any) -> None:
    """
    Initialize the XSD type mapping with the owlready2 locstr type.
    This should be called after owlready2 is imported.
    
    Args:
        locstr_type: The owlready2 locstr type
    """
    global XSD_TYPE_MAP
    
    XSD_TYPE_MAP.update({
        "xsd:string": str,
        "xsd:decimal": float,
        "xsd:double": float,
        "xsd:float": float,
        "xsd:integer": int,
        "xsd:int": int,
        "xsd:long": int,
        "xsd:short": int,
        "xsd:byte": int,
        "xsd:nonNegativeInteger": int,
        "xsd:positiveInteger": int,
        "xsd:negativeInteger": int,
        "xsd:nonPositiveInteger": int,
        "xsd:unsignedLong": int,
        "xsd:unsignedInt": int,
        "xsd:unsignedShort": int,
        "xsd:unsignedByte": int,
        "xsd:dateTime": datetime,
        "xsd:date": date,
        "xsd:time": time,
        "xsd:boolean": bool,
        "xsd:anyURI": str,
        "xsd:string (with lang tag)": locstr_type,
    })
