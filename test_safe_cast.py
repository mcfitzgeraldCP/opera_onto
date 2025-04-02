from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Type

def safe_cast(value: Any, target_type: type, default: Any = None) -> Any:
    if value is None or value == '':
        return default
    try:
        original_value_repr = repr(value)  # For logging
        value_str = str(value).strip()

        if target_type is str:
            return value_str
        if target_type is int:
            # Handle potential floats in data like '224.0' -> 224
            try:
                return int(float(value_str))
            except ValueError:
                # Maybe it was already an int disguised as string?
                return int(value_str)
        if target_type is float:
            # Handles standard float conversion
            return float(value_str)
        
        # Final fallback cast attempt
        return target_type(value_str)

    except (ValueError, TypeError, InvalidOperation) as e:
        print(f'Failed to cast {value} to {target_type.__name__}: {e}')
        return default
    except Exception as e:
        print(f'Unexpected error casting {value} to {target_type.__name__}: {e}')
        return default

# Test cases
test_cases = [
    ('0', float),
    ('0.0', float),
    ('0.116667', float),
    ('0', int),
    ('0.0', int),
    ('0.116667', int)
]

print("Testing safe_cast function with various numeric values...")
for value, type_to_cast in test_cases:
    result = safe_cast(value, type_to_cast)
    print(f'Value: {value}, Type: {type_to_cast.__name__}, Result: {result}, Result Type: {type(result).__name__}') 