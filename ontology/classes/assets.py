"""Manufacturing assets class definitions."""

import owlready2 as owl
from ontology.core import onto

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:

    class ManufacturingAsset(owl.Thing):
        """Base class for all manufacturing assets in the system.

        The manufacturing asset hierarchy is:
        Plant → Focus Factory → Physical Area → Line → Equipment

        Where:
        - Plant is the highest level manufacturing facility
        - Focus Factory is a specialized production area within a plant that produces different products
        - Physical Area is an area within a focus factory that produces different components
        - Line is a production line within an area that assembles or finishes parts of a product
        - Equipment is an individual machine on a line with a specific function
        """

        pass

    class Plant(ManufacturingAsset):
        """A manufacturing plant/facility entity.

        Plants are the highest level entity and can contain multiple focus factories.
        """

        pass

    class Line(ManufacturingAsset):
        """A production line within a plant.

        Lines are part of a physical area that produce or finish parts or finished products.
        """

        pass

    class Equipment(ManufacturingAsset):
        """A specific piece of equipment within a line.

        Equipment is the lowest level entity and performs specific functions (e.g., filling, packing).
        Equipment is meaningfully sequenced on a line, with upstream/downstream relationships.
        """

        pass


# Export classes for easy import
__all__ = ["ManufacturingAsset", "Plant", "Line", "Equipment"]
