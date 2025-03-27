"""Date and time utility functions."""

from datetime import datetime
import pandas as pd
from typing import Optional


def parse_datetime_with_tz(timestamp_str: Optional[str]) -> Optional[datetime]:
    """Parse timestamps with timezone information.

    Args:
        timestamp_str: Timestamp string in format 'YYYY-MM-DD HH:MM:SS.fff +/-HHMM'

    Returns:
        datetime object or None if parsing fails
    """
    if pd.isna(timestamp_str) or not timestamp_str:
        return None
    try:
        # Primary attempt: Remove colon from offset if present
        parts = timestamp_str.rsplit(" ", 1)
        dt_part = parts[0]
        tz_part = parts[1]

        # Ensure tz_part is in +/-HHMM format (no colon)
        if ":" in tz_part:
            tz_part_no_colon = tz_part.replace(":", "")
        else:
            tz_part_no_colon = tz_part

        # Check if it looks like a valid offset (+/- followed by 4 digits)
        if (
            len(tz_part_no_colon) == 5
            and tz_part_no_colon[0] in ("+", "-")
            and tz_part_no_colon[1:].isdigit()
        ):
            timestamp_str_fixed = f"{dt_part}{tz_part_no_colon}"
            dt_obj = datetime.strptime(timestamp_str_fixed, "%Y-%m-%d %H:%M:%S.%f%z")
            return dt_obj
        else:
            raise ValueError("Timezone offset not in expected +/-HHMM format")

    except Exception as e1:
        # Fallback 1: Try ISO format
        try:
            iso_str = timestamp_str
            if " " in dt_part:
                iso_str = timestamp_str.replace(" ", "T", 1)

            dt_obj = datetime.fromisoformat(iso_str)
            if dt_obj.tzinfo is None:
                print(
                    f"Warning: Parsed timestamp '{timestamp_str}' as naive datetime using fromisoformat fallback."
                )
            return dt_obj
        except Exception as e2:
            # Fallback 2: Try parsing without timezone
            try:
                dt_obj = datetime.strptime(dt_part, "%Y-%m-%d %H:%M:%S.%f")
                print(
                    f"Warning: Parsed timestamp '{timestamp_str}' as naive datetime (final fallback)."
                )
                return dt_obj
            except Exception as e3:
                print(
                    f"Error parsing timestamp '{timestamp_str}': Primary error: {e1}, Fallback errors: {e2} / {e3}"
                )
                return None
