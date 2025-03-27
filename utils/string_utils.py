"""String utility functions."""

import re
import pandas as pd
from typing import Optional, Any
import logging


def parse_equipment_base_type(equipment_name: str, line_name: str) -> Optional[str]:
    """Extract the base equipment type from the full equipment name.

    Args:
        equipment_name: Full equipment name (e.g., 'FIPCO001_Cartoner')
        line_name: Line name (e.g., 'FIPCO001')

    Returns:
        Base equipment type (e.g., 'Cartoner') or None if parsing fails
    """
    logger = logging.getLogger(__name__)

    if not isinstance(equipment_name, str) or not isinstance(line_name, str):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Invalid input types - equipment_name: {type(equipment_name)}, line_name: {type(line_name)}"
            )
        return None

    # Remove any whitespace
    equipment_name = equipment_name.strip()
    line_name = line_name.strip()

    # List of known equipment types to check for
    known_types = [
        "Filler",
        "Cartoner",
        "Bundler",
        "CasePacker",
        "CaseFormer",
        "CaseSealer",
        "Palletizer",
    ]

    # Check if equipment name contains the line name followed by underscore
    if line_name and equipment_name.startswith(f"{line_name}_"):
        # Extract the part after line name and underscore
        base_type = equipment_name[len(line_name) + 1 :]

        # Remove any trailing numbers (e.g., Cartoner2 -> Cartoner)
        base_type = re.sub(r"\d+$", "", base_type)

        # Log the extracted type at debug level
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Extracted equipment type '{base_type}' from '{equipment_name}'"
            )

        return base_type

    # If equipment name contains an underscore (but doesn't match the pattern above)
    elif "_" in equipment_name:
        # Split by underscore and take the last part
        parts = equipment_name.split("_")
        # The base type should be the last part after the underscore
        base = parts[-1]
        # Remove any trailing numbers (e.g., Cartoner2 -> Cartoner)
        base = re.sub(r"\d+$", "", base)

        # Log the extracted type at debug level
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Extracted equipment type '{base}' from underscore-separated name '{equipment_name}'"
            )

        return base

    # If equipment name equals line name (e.g., 'FIPCO001')
    if equipment_name == line_name:
        # This is a common case, only log in detailed debug mode
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Equipment name '{equipment_name}' equals line name, cannot determine type"
            )
        return "Unknown"

    # Try to extract known equipment types from the name
    for known_type in known_types:
        if known_type.lower() in equipment_name.lower():
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"Found known type '{known_type}' in equipment name '{equipment_name}'"
                )
            return known_type

    # If we can't determine the type, log and return default
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            f"Equipment name '{equipment_name}' does not match expected patterns for line '{line_name}'"
        )
    return "Unknown"


def clean_string_value(value: Any) -> Optional[str]:
    """Clean string values, handling None and NaN cases.

    Args:
        value: Any value that might be converted to string

    Returns:
        Cleaned string or None if value is invalid
    """
    if pd.isna(value) or value is None:
        return None
    return str(value).strip()
