"""Configuration for equipment sequences and relationships."""

from typing import Dict, Any


def get_equipment_type_sequence_order() -> Dict[str, int]:
    """Define the typical/default sequence order for known equipment types.

    Returns:
        Dictionary mapping equipment type to its typical sequence number
    """
    return {
        "Filler": 1,
        "Cartoner": 2,
        "Bundler": 3,
        "CaseFormer": 4,
        "CasePacker": 5,
        "CaseSealer": 6,
        "Palletizer": 7,
    }


def get_equipment_sequence_overrides() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Define line-specific equipment sequence overrides.

    Only specify overrides when different from default order.

    Returns:
        Nested dictionary of line-specific equipment sequence configurations
    """
    return {
        # Example: VIPCO012 has a non-standard sequence
        "VIPCO012": {
            "TubeMaker": {"order": 1, "downstream": "CasePacker"},
            "CasePacker": {"order": 2, "upstream": "TubeMaker"},
        },
        # Example: FIPCO006 skips Cartoner, direct Filler->CasePacker
        "FIPCO006": {
            "Filler": {"order": 1, "downstream": "CasePacker"},
            "CasePacker": {"order": 2, "upstream": "Filler"},
        },
    }
