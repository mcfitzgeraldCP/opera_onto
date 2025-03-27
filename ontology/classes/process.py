"""Process context class definitions."""

import owlready2 as owl
from ontology.core import onto

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:

    class ProcessContext(owl.Thing):
        """Base class for production process context entities."""

        pass

    class Material(ProcessContext):
        """Material being processed."""

        pass

    class ProductionOrder(ProcessContext):
        """Production order being executed."""

        pass

    class Crew(ProcessContext):
        """Crew operating equipment during a shift."""

        pass


# Export classes for easy import
__all__ = ["ProcessContext", "Material", "ProductionOrder", "Crew"]
