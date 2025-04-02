"""
Ontology Generator Configuration

This module contains constants, mappings, and configuration settings for the ontology generator.
"""
from typing import Dict, Any, Type, Optional
from datetime import datetime, date, time

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
    "Created new individual"
]

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
DEFAULT_EQUIPMENT_SEQUENCE: Dict[str, int] = {
    "Filler": 1,
    "Cartoner": 2,
    "Bundler": 3,
    "CaseFormer": 4,
    "CasePacker": 5,
    "CaseSealer": 6,
    "Palletizer": 7,
    # Add any other classes with default positions if needed
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
