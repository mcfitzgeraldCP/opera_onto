"""General settings for the plant_owl project."""

from typing import Dict, Any


def get_ontology_settings() -> Dict[str, Any]:
    """Get general ontology settings.

    Returns:
        Dictionary of settings for the ontology
    """
    return {
        "ontology_iri": "http://example.org/manufacturing_revised_ontology.owl",
        "default_output_file": "manufacturing_ontology_revised_populated.owl",
        "format": "rdfxml",
    }
