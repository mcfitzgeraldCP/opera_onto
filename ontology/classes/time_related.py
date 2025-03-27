"""Time-related class definitions."""

import owlready2 as owl
from ontology.core import onto
from ontology.classes.process import ProcessContext

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:

    class TimeRelated(owl.Thing):
        """Base class for time-related entities."""

        pass

    class TimeInterval(TimeRelated):
        """Time interval with start and end times."""

        pass

    class Shift(TimeRelated, ProcessContext):
        """Production shift, which involves Crew and affects Records."""

        pass


# Export classes for easy import
__all__ = ["TimeRelated", "TimeInterval", "Shift"]
