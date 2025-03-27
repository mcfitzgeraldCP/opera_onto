"""Location-related class definitions."""

import owlready2 as owl
from ontology.core import onto

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:

    class Location(owl.Thing):
        """Base class for all location entities."""

        pass

    class Country(Location):
        """Country location."""

        pass

    class StrategicLocation(Location):
        """Strategic location classification."""

        pass

    class PhysicalArea(Location):
        """Physical area within a plant (e.g., PACK, OralCare).

        In the manufacturing hierarchy:
        - A PhysicalArea is part of a Focus Factory
        - A PhysicalArea contains one or more production Lines
        - PhysicalAreas represent areas that produce different components of a product
        """

        pass  # From PHYSICAL_AREA


# Export classes for easy import
__all__ = ["Location", "Country", "StrategicLocation", "PhysicalArea"]
