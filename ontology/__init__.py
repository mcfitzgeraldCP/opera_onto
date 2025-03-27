"""Ontology definition for manufacturing assets and events."""

from ontology.core import onto, ONTOLOGY_IRI

# Import all classes for easy access
from ontology.classes import *

# Import all properties for easy access
from ontology.properties import *

# Import helper functions
from ontology.helpers import get_or_create_instance

__all__ = [
    "onto",
    "ONTOLOGY_IRI",
    "get_or_create_instance",
]
