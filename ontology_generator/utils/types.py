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
                # Check for common problematic patterns first
                if value_str.lower() in ['', 'null', 'none', 'na', 'n/a', '?']:
                    pop_logger.warning(f"Empty or null datetime value: {original_value_repr}")
                    return default
                
                # Check for common malformed date patterns
                if re.match(r'^\d{1,2}/\d{1,2}$', value_str):  # Just MM/DD with no year
                    pop_logger.warning(f"Incomplete date without year: {original_value_repr}")
                    return default
                
                # Additional cleanup for common issues that dateutil might misinterpret
                cleaned_value = value_str
                # Remove any double spaces that might confuse the parser
                cleaned_value = re.sub(r'\s+', ' ', cleaned_value).strip()
                
                # No need for extensive pre-cleaning or format list with dateutil
                # It handles various formats, including spaces and timezones
                parsed_dt = dateutil_parser.parse(cleaned_value)

                # Capture parsing details for diagnostic logging
                has_timezone = parsed_dt.tzinfo is not None
                timezone_name = str(parsed_dt.tzinfo) if has_timezone else "None"

                # dateutil returns an AWARE datetime if offset is present.
                # owlready2 stores naive datetimes.
                # Maintain existing behavior: make it naive (loses original offset info).
                if has_timezone:
                    pop_logger.debug(f"Parsed datetime {original_value_repr} with timezone {timezone_name}, storing as naive datetime.")
                    parsed_dt = parsed_dt.replace(tzinfo=None)
                else:
                    pop_logger.debug(f"Parsed datetime {original_value_repr} without timezone, storing as naive datetime.")

                pop_logger.debug(f"Successfully parsed datetime '{original_value_repr}' → {parsed_dt}")
                return parsed_dt

            except (ParserError, ValueError, TypeError) as e:  # Catch errors from dateutil and potential downstream issues
                # Provide more detailed diagnostic information about the failed parse
                pop_logger.warning(f"Could not parse datetime '{original_value_repr}': {e}")
                
                # Try some common patterns explicitly as a fallback
                try:
                    # Try to identify the pattern for better error reporting
                    if '/' in value_str:
                        pattern = "MM/DD/YYYY or DD/MM/YYYY"
                    elif '-' in value_str:
                        pattern = "YYYY-MM-DD"
                    elif '.' in value_str:
                        pattern = "DD.MM.YYYY"
                    else:
                        pattern = "unknown"
                    
                    pop_logger.warning(f"Original datetime string appears to use {pattern} format. Check data source for consistency.")
                except:
                    pass
                    
                return default
            except Exception as e:  # Catch any other unexpected errors
                pop_logger.error(f"Unexpected error parsing datetime '{original_value_repr}': {e}", exc_info=False)
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
        pop_logger.warning(f"Sanitized name for '{name_str}' became empty or invalid. Using fallback hash: {safe_name}")
        
    return safe_name

# TKT-003: Add unit tests for sanitize_name function
# These tests can be run directly with Python to verify the function works as expected
def _test_sanitize_name():
    """
    Test suite for sanitize_name function.
    Run this function directly to verify sanitize_name behavior.
    """
    test_cases = [
        # (input, expected_output, description)
        (None, "unnamed", "None value"),
        ("", "unnamed", "Empty string"),
        ("   ", "unnamed", "Whitespace only"),
        ("Simple", "Simple", "Simple alphanumeric"),
        ("Simple Name", "Simple_Name", "Spaces to underscore"),
        ("Name-With-Hyphens", "Name-With-Hyphens", "Preserve hyphens"),
        ("Name.With.Dots", "Name.With.Dots", "Preserve periods"),
        ("Name_With_Underscores", "Name_With_Underscores", "Preserve underscores"),
        ("123StartsWithNumber", "_123StartsWithNumber", "Prepend underscore to numbers"),
        ("-StartsWithHyphen", "_-StartsWithHyphen", "Prepend underscore to hyphen"),
        ("Special@#$%^&*()Chars", "Special_____Chars", "Replace special chars with underscores"),
        ("<>:\"/\\|?*", "________", "All special chars become underscores"),
        ("Mixed<>:\"/\\|?*AndLetters", "Mixed________AndLetters", "Mixed content"),
        ("Üñîçøδê", "____", "Unicode characters"),  # Note: This case is strict - non-ASCII removed
        # Edge cases
        ("   Trim   Spaces   ", "Trim___Spaces", "Trim and collapse spaces"),
        ("<all special>", "_all_special_", "Special chars at boundaries"),
    ]
    
    passed = 0
    failed = 0
    
    print("\n===== TESTING sanitize_name FUNCTION =====")
    for i, (input_val, expected, desc) in enumerate(test_cases):
        result = sanitize_name(input_val)
        if result == expected:
            passed += 1
            print(f"✓ Test {i+1}: {desc}")
        else:
            failed += 1
            print(f"✗ Test {i+1}: {desc}")
            print(f"  Input: {repr(input_val)}")
            print(f"  Expected: {repr(expected)}")
            print(f"  Got: {repr(result)}")
    
    # Test for consistency - same input should always yield same output
    consistency_check = sanitize_name("Test String")
    for i in range(5):
        if sanitize_name("Test String") != consistency_check:
            failed += 1
            print(f"✗ Consistency check failed on iteration {i+1}")
            break
    else:
        passed += 1
        print("✓ Consistency check passed")
    
    # Hash fallback test (these inputs clean to empty string)
    print("\nHash fallback test (unpredictable output):")
    empty_after_clean = "!@#$%^&*()"
    fallback_result = sanitize_name(empty_after_clean)
    print(f"Input: {repr(empty_after_clean)}")
    print(f"Result: {repr(fallback_result)}")
    if fallback_result.startswith("UnnamedData_"):
        passed += 1
        print("✓ Hash fallback test passed")
    else:
        failed += 1
        print("✗ Hash fallback test failed")
    
    print(f"\nTests complete: {passed} passed, {failed} failed")
    print("========================================\n")
    
    return passed, failed

# Run tests automatically if this module is executed directly
if __name__ == "__main__":
    _test_sanitize_name()
