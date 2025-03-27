"""Data preprocessing utilities for the manufacturing ontology."""

import pandas as pd
from typing import List, Optional
import logging
import re
from utils.string_utils import parse_equipment_base_type

logger = logging.getLogger(__name__)


def preprocess_manufacturing_data(df: pd.DataFrame) -> pd.DataFrame:
    """Preprocess manufacturing data for ontology population.

    Handles data type conversion, cleaning, and basic validation.

    Args:
        df: Raw DataFrame loaded from CSV

    Returns:
        Preprocessed DataFrame ready for ontology mapping
    """
    # Make a copy to avoid modifying the original
    processed_df = df.copy()

    # Process string ID columns that should be strings
    _convert_id_columns(processed_df)

    # Process boolean columns
    _convert_boolean_columns(processed_df)

    # Process numeric columns
    _convert_numeric_columns(processed_df)

    # Process string columns
    _convert_string_columns(processed_df)

    # Extract equipment base types
    _extract_equipment_base_types(processed_df)

    return processed_df


def _convert_id_columns(df: pd.DataFrame) -> None:
    """Convert ID columns to strings."""
    for col in ["EQUIPMENT_ID", "PRODUCTION_ORDER_ID"]:
        if col in df.columns:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce")
                .astype("Int64")
                .astype(str)
                .replace("<NA>", None)
            )


def _convert_boolean_columns(df: pd.DataFrame) -> None:
    """Convert boolean columns to proper boolean type."""
    if "RAMPUP_FLAG" in df.columns:
        df["RAMPUP_FLAG"] = df["RAMPUP_FLAG"].astype(bool)


def _convert_numeric_columns(df: pd.DataFrame) -> None:
    """Convert numeric columns to proper float type."""
    numeric_cols = [
        "TOTAL_TIME_SECONDS",
        "TOTAL_TIME",
        "BUSINESS_EXTERNAL_TIME",
        "PLANT_AVAILABLE_TIME",
        "EFFECTIVE_RUNTIME",
        "PLANT_DECISION_TIME",
        "PRODUCTION_AVAILABLE_TIME",
        "GOOD_PRODUCTION_QTY",
        "REJECT_PRODUCTION_QTY",
        "DOWNTIME",
        "RUN_TIME",
        "NOT_ENTERED",
        "WAITING_TIME",
        "PLANT_EXPERIMENTATION",
        "ALL_MAINTENANCE",
        "AUTONOMOUS_MAINTENANCE",
        "PLANNED_MAINTENANCE",
        "CHANGEOVER_DURATION",
        "CLEANING_AND_SANITIZATION",
        "LUNCH_AND_BREAK",
        "LUNCH",
        "BREAK",
        "MEETING_AND_TRAINING",
        "NO_DEMAND",
        "PRIMARY_CONV_FACTOR",
        "PRODUCTION_ORDER_RATE",
        "SHIFT_DURATION_MIN",
        "UOM_ST",
        "UOM_ST_SAP",
        "TP_UOM",
        "PLANT_LATITUDE",
        "PLANT_LONGITUDE",
        "CHANGEOVER_COUNT",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")


def _convert_string_columns(df: pd.DataFrame) -> None:
    """Convert string columns to clean strings."""
    string_cols = [
        "LINE_NAME",
        "EQUIPMENT_NAME",
        "PLANT",
        "DOWNTIME_DRIVER",
        "OPERA_TYPE",
        "GH_AREA",
        "GH_CATEGORY",
        "GH_FOCUSFACTORY",
        "PHYSICAL_AREA",
        "EQUIPMENT_TYPE",
        "EQUIPMENT_BASE_TYPE",
        "EQUIPMENT_MODEL",
        "COMPLEXITY",
        "MODEL",
        "MATERIAL_ID",
        "SHORT_MATERIAL_ID",
        "SIZE_TYPE",
        "MATERIAL_UOM",
        "PRODUCTION_ORDER_DESC",
        "PRODUCTION_ORDER_UOM",
        "UTIL_STATE_DESCRIPTION",
        "UTIL_REASON_DESCRIPTION",
        "UTIL_ALT_LANGUAGE_REASON",
        "CO_TYPE",
        "CO_ORIGINAL_TYPE",
        "SHIFT_NAME",
        "CREW_ID",
        "PLANT_DESCRIPTION",
        "PLANT_STRATEGIC_LOCATION",
        "PLANT_COUNTRY",
        "PLANT_COUNTRY_DESCRIPTION",
        "PLANT_FACILITY_TYPE",
        "PLANT_POSTAL_CODE",
        "PLANT_PURCHASING_ORGANIZATION",
        "PLANT_STRATEGIC_LOCATION_DESCRIPTION",
        "PLANT_DIVISION",
        "PLANT_DIVISION_DESCRIPTION",
        "PLANT_SUB_DIVISION",
        "PLANT_SUB_DIVISION_DESCRIPTION",
        "AE_MODEL_CATEGORY",
        "SOURCE_DATASET",
        "SOURCE_DATASET_FUNCTIONAL_AREA",
        "SOURCE_DATASET_SUBFUNCTIONAL_AREA",
    ]
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("nan", None).replace("None", None)


def _extract_equipment_base_types(df: pd.DataFrame) -> None:
    """Extract and populate the EQUIPMENT_BASE_TYPE field based on equipment name patterns.

    If EQUIPMENT_BASE_TYPE is already populated with a non-null value, it will be preserved.
    Otherwise, it will be calculated from the equipment name and line name.

    Args:
        df: DataFrame to process
    """
    # Skip if we don't have the necessary columns
    if "EQUIPMENT_NAME" not in df.columns or "LINE_NAME" not in df.columns:
        logger.warning(
            "Cannot extract equipment base types: missing EQUIPMENT_NAME or LINE_NAME columns"
        )
        return

    # Create EQUIPMENT_BASE_TYPE column if it doesn't exist
    if "EQUIPMENT_BASE_TYPE" not in df.columns:
        df["EQUIPMENT_BASE_TYPE"] = None

    # Track statistics
    total_equipment = 0
    detected_types = 0

    # Process each row
    for idx, row in df.iterrows():
        # Skip if equipment base type is already populated with a non-null value
        if pd.notna(row["EQUIPMENT_BASE_TYPE"]) and row["EQUIPMENT_BASE_TYPE"] not in [
            "nan",
            "None",
            "Unknown",
        ]:
            continue

        # Skip line-level records
        if row["EQUIPMENT_TYPE"] == "LINE" or row["EQUIPMENT_NAME"] == row["LINE_NAME"]:
            continue

        # Count actual equipment records
        total_equipment += 1

        # Extract equipment base type
        equipment_name = row["EQUIPMENT_NAME"]
        line_name = row["LINE_NAME"]

        if pd.isna(equipment_name) or pd.isna(line_name):
            continue

        equipment_base_type = parse_equipment_base_type(
            str(equipment_name), str(line_name)
        )

        # Only set if we found a type other than Unknown
        if equipment_base_type and equipment_base_type != "Unknown":
            df.at[idx, "EQUIPMENT_BASE_TYPE"] = equipment_base_type
            detected_types += 1

    # Log results
    if total_equipment > 0:
        logger.info(
            f"Extracted equipment types for {detected_types}/{total_equipment} equipment records ({detected_types/total_equipment:.1%})"
        )
