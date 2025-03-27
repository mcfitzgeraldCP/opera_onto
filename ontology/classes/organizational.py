"""Organizational unit class definitions."""

import owlready2 as owl
from ontology.core import onto

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:

    class OrganizationalUnit(owl.Thing):
        """Base class for organizational units."""

        pass

    class Division(OrganizationalUnit):
        """Top-level organizational division."""

        pass

    class SubDivision(OrganizationalUnit):
        """Sub-division within a division."""

        pass

    class FocusFactory(OrganizationalUnit):
        """Focus factory (e.g., TPST from GH_FOCUSFACTORY).

        In the manufacturing hierarchy:
        - A FocusFactory is contained within a Plant
        - A FocusFactory contains multiple PhysicalAreas
        - FocusFactories produce different products
        - FocusFactories represent a major organizational division of manufacturing capabilities
        """

        pass

    class GlobalHierarchyArea(OrganizationalUnit):
        """Global hierarchy area (e.g., TUBE/PACK from GH_AREA)."""

        pass

    class GlobalHierarchyCategory(OrganizationalUnit):
        """Global hierarchy category (e.g., OC from GH_CATEGORY)."""

        pass

    class PurchasingOrganization(OrganizationalUnit):
        """Purchasing organization."""

        pass


# Export classes for easy import
__all__ = [
    "OrganizationalUnit",
    "Division",
    "SubDivision",
    "FocusFactory",
    "GlobalHierarchyArea",
    "GlobalHierarchyCategory",
    "PurchasingOrganization",
]
