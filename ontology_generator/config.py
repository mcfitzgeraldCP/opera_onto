"""
Ontology Generator Configuration

This module contains constants, mappings, and configuration settings for the ontology generator.
It defines column names, equipment sequences, language mappings, and various other configuration
parameters used throughout the ontology generation process.
"""
from typing import Dict, Any, Type, Optional
from datetime import datetime, date, time
import logging

# -----------------------------------------------------------------------------
# GENERAL CONFIGURATION
# -----------------------------------------------------------------------------
DEFAULT_ONTOLOGY_IRI = "http://example.com/manufacturing_ontology.owl"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
SPEC_PARENT_CLASS_COLUMN = 'Parent Class'  # Column name for hierarchy definition

# -----------------------------------------------------------------------------
# SPECIFICATION COLUMN NAMES
# -----------------------------------------------------------------------------
# Entity and property identification
SPEC_COL_ENTITY = "Proposed OWL Entity"
SPEC_COL_PROPERTY = "Proposed OWL Property"
SPEC_COL_PROP_TYPE = "OWL Property Type"

# Property details
SPEC_COL_RAW_DATA = "Raw Data Column Name"
SPEC_COL_TARGET_RANGE = "Target/Range (xsd:) / Target Class"
SPEC_COL_PROP_CHARACTERISTICS = "OWL Property Characteristics"
SPEC_COL_INVERSE_PROPERTY = "Inverse Property"
SPEC_COL_DOMAIN = "Domain"
SPEC_COL_TARGET_LINK_CONTEXT = "Target Link Context"
SPEC_COL_PROGRAMMATIC = "Programmatic"

# Classification and documentation
SPEC_COL_LOGICAL_GROUP = "Logical Group"
SPEC_COL_NOTES = "Notes/Considerations"
SPEC_COL_ISA95_CONCEPT = "ISA-95 Concept"

# -----------------------------------------------------------------------------
# LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
# Warning messages to suppress in logs
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
    
    # Get the root logger and add the filter
    root_logger = logging.getLogger()
    root_logger.addFilter(message_filter)
    
    # Add filters to specific logger instances
    loggers = [
        "ontology_generator.population",
        "ontology_generator.population.row_processor",
        "ontology_generator.population.core",
        "event_linking"
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.addFilter(message_filter)

# -----------------------------------------------------------------------------
# LANGUAGE CONFIGURATION
# -----------------------------------------------------------------------------
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
    "China": "zh"
}
DEFAULT_LANGUAGE = "en"  # Default language if country not found in mapping

# -----------------------------------------------------------------------------
# EQUIPMENT CONFIGURATION
# -----------------------------------------------------------------------------
# Default equipment sequence represents typical physical order on manufacturing line
DEFAULT_EQUIPMENT_SEQUENCE: Dict[str, int] = {
    "Filler": 1,        # First in typical sequence
    "Cartoner": 2,      # Second in typical sequence
    "Bundler": 3,       # Third in typical sequence
    "CaseFormer": 4,    # Fourth in typical sequence
    "CasePacker": 5,    # Fifth in typical sequence
    "CaseSealer": 6,    # Sixth in typical sequence
    "Palletizer": 7     # Last in typical sequence
}

# Known equipment classes for identification and matching
KNOWN_EQUIPMENT_CLASSES = list(DEFAULT_EQUIPMENT_SEQUENCE.keys())

# Maps specific patterns in equipment names to their classes
EQUIPMENT_NAME_TO_CLASS_MAP = {
    "_Filler": "Filler",
    "_Cartoner": "Cartoner",
    "_Bundler": "Bundler",
    "_CaseFormer": "CaseFormer",
    "_CasePacker": "CasePacker",
    "_CaseSealer": "CaseSealer",
    "_Palletizer": "Palletizer"
}

# Line-specific equipment sequences that override the default
LINE_SPECIFIC_EQUIPMENT_SEQUENCE: Dict[str, Dict[str, int]] = {
    "Line1": {
        "Filler": 1,        # First position
        "Cartoner": 2,      # Second position
        "Bundler": 3,       # Third position
        "CaseFormer": 4,    # Fourth position
        "CasePacker": 5,    # Fifth position
        "CaseSealer": 6,    # Sixth position
        "Palletizer": 7     # Seventh position
    }
}

# -----------------------------------------------------------------------------
# XSD TYPE MAPPING
# -----------------------------------------------------------------------------
# Initialized when importing required modules to avoid circular imports
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
        "xsd:string (with lang tag)": locstr_type
    })
