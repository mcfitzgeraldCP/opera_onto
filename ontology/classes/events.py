"""Event record class definitions."""

import owlready2 as owl
from ontology.core import onto

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:

    class EventRecord(owl.Thing):
        """Base class for manufacturing event records."""

        pass


# Export classes for easy import
__all__ = ["EventRecord"]
