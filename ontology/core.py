"""Core ontology module defining the base ontology and shared components."""

import owlready2 as owl
from typing import Optional
from config.settings import get_ontology_settings

# Set important owlready2 options
# Disable use of annotation triples, which can help prevent some issues
# with multiple inheritance and property assignments
owl.JAVA_EXE = None  # Disable Java-based reasoner if not needed

# Get ontology settings
settings = get_ontology_settings()

# Create a new ontology
ONTOLOGY_IRI = settings["ontology_iri"]
onto = owl.get_ontology(ONTOLOGY_IRI)

# Re-export ontology for easy import
__all__ = ["onto", "ONTOLOGY_IRI"]
