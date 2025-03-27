"""Data loading utilities for the manufacturing ontology."""

import pandas as pd
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


def load_csv_data(csv_path: str) -> pd.DataFrame:
    """Load and perform basic preprocessing on CSV data.

    Args:
        csv_path: Path to the CSV file to load

    Returns:
        DataFrame with loaded data

    Raises:
        FileNotFoundError: If the CSV file cannot be found
        ValueError: If the CSV cannot be parsed correctly
    """
    logger.info(f"Loading data from {csv_path}")
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        logger.info(f"Loaded {len(df)} rows")
        return df
    except FileNotFoundError:
        logger.error(f"Error: {csv_path} not found")
        raise
    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        raise ValueError(f"Failed to parse CSV: {e}")
