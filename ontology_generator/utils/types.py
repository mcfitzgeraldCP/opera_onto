"""
Type conversion utilities for the ontology generator.

This module provides functions for safe type conversion and handling.
"""
import re
from datetime import datetime, date, time
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Type, List, Dict, TypeVar, Union

from dateutil import parser as dateutil_parser
from dateutil.parser import ParserError

from ontology_generator.utils.logging import pop_logger

T = TypeVar('T')

def safe_cast(value: Any, target_type: Type[T], default: Optional[T] = None) -> Optional[T]:
    """
    Safely casts a value to a target type, returning default on failure.
    
    Args:
        value: The value to cast
        target_type: The target type to cast to
        default: The default value to return on failure
        
    Returns:
        The cast value, or the default if casting fails
    """
    if value is None or value == '':
        return default
    try:
        original_value_repr = repr(value)  # For logging
        value_str = str(value).strip()

        if target_type is str:
            return value_str
        if target_type is int:
            # Handle potential floats in data like '224.0' -> 224
            # Also handle direct integers or strings representing integers
            try:
                # TKT-006: Handle empty strings, whitespace, etc.
                if not value_str or value_str.isspace():
                    return default
                
                # Special case for numeric metrics: treat "" or "0" as 0
                if value_str == "" or value_str == "0":
                    return 0
                    
                return int(float(value_str))
            except ValueError:
                # Maybe it was already an int disguised as string?
                return int(value_str)
        if target_type is float:
            # TKT-006: Handle empty strings, whitespace, etc.
            if not value_str or value_str.isspace():
                return default
                
            # Special case for numeric metrics: treat "" or "0" as 0.0
            if value_str == "" or value_str == "0":
                return 0.0
                
            # Handles standard float conversion
            return float(value_str)
        # Note: xsd:decimal maps to float based on XSD_TYPE_MAP
        if target_type is bool:
            val_lower = value_str.lower()
            if val_lower in ['true', '1', 't', 'y', 'yes']:
                return True
            elif val_lower in ['false', '0', 'f', 'n', 'no']:
                return False
            else:
                pop_logger.warning(f"Could not interpret {original_value_repr} as boolean.")
                return None  # Explicitly return None for uninterpretable bools
        if target_type is datetime:
            # --- Use dateutil.parser for robust parsing ---
            try:
                # No need for extensive pre-cleaning or format list with dateutil
                # It handles various formats, including spaces and timezones
                parsed_dt = dateutil_parser.parse(value_str)

                # dateutil returns an AWARE datetime if offset is present.
                # owlready2 stores naive datetimes.
                # Maintain existing behavior: make it naive (loses original offset info).
                if parsed_dt.tzinfo:
                    pop_logger.debug(f"Parsed datetime {original_value_repr} with timezone {parsed_dt.tzinfo}, storing as naive datetime.")
                    parsed_dt = parsed_dt.replace(tzinfo=None)
                else:
                    pop_logger.debug(f"Parsed datetime {original_value_repr} without timezone, storing as naive datetime.")

                pop_logger.debug(f"Successfully parsed datetime {original_value_repr} using dateutil -> {parsed_dt}")
                return parsed_dt

            except (ParserError, ValueError, TypeError) as e:  # Catch errors from dateutil and potential downstream issues
                pop_logger.warning(f"Could not parse datetime string {original_value_repr} using dateutil parser: {e}")
                return default
            except Exception as e:  # Catch any other unexpected errors
                pop_logger.error(f"Unexpected error parsing datetime {original_value_repr} with dateutil: {e}", exc_info=False)
                return default
            # --- End of dateutil parsing block ---

        if target_type is date:
            try:
                # Try ISO first
                return date.fromisoformat(value_str)  # Assumes YYYY-MM-DD
            except ValueError:
                # Try other common formats if needed
                try:
                    dt_obj = datetime.strptime(value_str, "%m/%d/%Y")  # Example alternative
                    return dt_obj.date()
                except ValueError:
                    pop_logger.warning(f"Could not parse date string {original_value_repr} as ISO or m/d/Y date.")
                    return default
        if target_type is time:
            try:
                # Try ISO first
                return time.fromisoformat(value_str)  # Assumes HH:MM:SS[.ffffff][+/-HH:MM]
            except ValueError:
                # Try other common formats if needed
                try:
                    dt_obj = datetime.strptime(value_str, "%H:%M:%S")  # Just H:M:S
                    return dt_obj.time()
                except ValueError:
                    pop_logger.warning(f"Could not parse time string {original_value_repr} as ISO or H:M:S time.")
                    return default

        # Final fallback cast attempt
        return target_type(value_str)

    except (ValueError, TypeError, InvalidOperation) as e:
        target_type_name = target_type.__name__ if target_type else "None"
        original_value_repr = repr(value)[:50] + ('...' if len(repr(value)) > 50 else '') # Added for clarity
        pop_logger.warning(f"Failed to cast {original_value_repr} to {target_type_name}: {e}. Returning default: {default}")
        return default
    except Exception as e:
        target_type_name = target_type.__name__ if target_type else "None"
        original_value_repr = repr(value)[:50] + ('...' if len(repr(value)) > 50 else '') # Added for clarity
        pop_logger.error(f"Unexpected error casting {original_value_repr} to {target_type_name}: {e}", exc_info=False)
        return default

def sanitize_name(name: Any) -> str:
    """
    Sanitizes a name to be valid for use in identifiers.
    
    Args:
        name: The name to sanitize
        
    Returns:
        A sanitized version of the name
    """
    if name is None or str(name).strip() == '':
        return "unnamed"
        
    # Convert to string and strip whitespace
    name_str = str(name).strip()
    
    # Replace spaces and common problematic chars with underscore
    safe_name = re.sub(r'\s+|[<>:"/\\|?*#%\']', '_', name_str)
    
    # Remove any remaining non-alphanumeric, non-hyphen, non-underscore chars (allows periods)
    safe_name = re.sub(r'[^\w\-._]', '', safe_name)
    
    # Ensure it doesn't start with a number or hyphen (common restriction)
    if safe_name and (safe_name[0].isdigit() or safe_name[0] == '-'):
        safe_name = "_" + safe_name
        
    # Check if empty after sanitization
    if not safe_name:
        fallback_hash = abs(hash(name_str))  # Hash the original string
        safe_name = f"UnnamedData_{fallback_hash}"
        
    return safe_name
