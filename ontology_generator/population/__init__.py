"""Population package for the ontology generator."""
from .sequence import setup_equipment_instance_relationships
from .row_processor import process_single_data_row_pass1, process_single_data_row_pass2

# List functions/classes to expose at the package level
__all__ = [
    # 'populate_ontology_from_data', # Removed - Defined in main.py
    'setup_equipment_instance_relationships',
    # Add other core components if needed, e.g., PopulationContext? No, likely used internally.
]
