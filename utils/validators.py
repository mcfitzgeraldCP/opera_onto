"""Data validation utility functions."""

import pandas as pd
from typing import Any, Optional


def clean_numeric_value(value: Any) -> Optional[float]:
    """Clean numeric values, handling None and NaN cases.

    Args:
        value: Any value that might be converted to float

    Returns:
        Cleaned float or None if value is invalid
    """
    if pd.isna(value) or value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def clean_boolean_value(value: Any) -> Optional[bool]:
    """Clean boolean values, handling None and NaN cases.

    Args:
        value: Any value that might be converted to boolean

    Returns:
        Cleaned boolean or None if value is invalid
    """
    if pd.isna(value) or value is None:
        return None
    try:
        return bool(value)
    except (ValueError, TypeError):
        return None
