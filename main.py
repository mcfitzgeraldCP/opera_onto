#!/usr/bin/env python3
"""Main entry point for the manufacturing ontology application."""
import argparse
import logging
import sys
from pathlib import Path
import owlready2 as owl

from ontology.core import onto, ONTOLOGY_IRI
from data.loaders import load_csv_data
from data.processors import preprocess_manufacturing_data
from data.mappers import map_row_to_ontology
from config.equipment_config import (
    get_equipment_type_sequence_order,
    get_equipment_sequence_overrides,
)
from config.settings import get_ontology_settings
from queries.equipment_queries import find_equipment_by_type, find_downstream_equipment

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Set specific logging levels for modules
logging.getLogger("data.mappers").setLevel(
    logging.INFO
)  # Reduce debug messages about missing times
logging.getLogger("utils.string_utils").setLevel(
    logging.DEBUG
)  # Enable detailed logging for equipment type detection
logging.getLogger("ontology.helpers").setLevel(
    logging.INFO
)  # Set level for ontology helpers


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Manufacturing Ontology Builder")
    parser.add_argument("--input", "-i", required=True, help="Input CSV file path")

    # Get default output file from settings
    settings = get_ontology_settings()
    default_output = settings.get("default_output_file", "manufacturing_ontology.owl")

    parser.add_argument(
        "--output", "-o", help="Output OWL file path", default=default_output
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    return parser.parse_args()


def main():
    """Main application entry point."""
    # Parse arguments
    args = parse_arguments()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Check if input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1

    try:
        # Load and preprocess data
        logger.info(f"Loading data from {input_path}")
        df = load_csv_data(args.input)

        logger.info("Preprocessing data")
        processed_df = preprocess_manufacturing_data(df)

        # Get configuration
        equipment_type_sequence_order = get_equipment_type_sequence_order()
        equipment_sequence_overrides = get_equipment_sequence_overrides()

        # Counters for statistics
        stats = {
            "total_rows": len(processed_df),
            "processed_rows": 0,
            "error_rows": 0,
            "missing_time_info": 0,
            "equipment_type_missing": 0,
            "line_level_records": 0,
            "equipment_with_type": 0,
        }

        # Create a counter for specific equipment types to track distribution
        equipment_type_counts = {}

        # Process each row
        logger.info("Populating ontology")
        row_count = len(processed_df)
        data_rows = processed_df.to_dict("records")

        for i, row_data in enumerate(data_rows):
            try:
                # Check for time info across different possible field patterns
                has_standard_time = row_data.get("START_TIME_UTC") and row_data.get(
                    "END_TIME_UTC"
                )

                # Check for event-specific time fields
                state_desc = row_data.get("UTIL_STATE_DESCRIPTION", "").upper()
                has_event_time = False

                if "DOWNTIME" in state_desc and (
                    row_data.get("DOWNTIME_START_UTC")
                    and row_data.get("DOWNTIME_END_UTC")
                ):
                    has_event_time = True
                elif "RUNNING" in state_desc and (
                    row_data.get("RUNTIME_START_UTC")
                    and row_data.get("RUNTIME_END_UTC")
                ):
                    has_event_time = True
                elif "CHANGEOVER" in state_desc and (
                    row_data.get("CHANGEOVER_START_UTC")
                    and row_data.get("CHANGEOVER_END_UTC")
                ):
                    has_event_time = True

                if not (has_standard_time or has_event_time):
                    stats["missing_time_info"] += 1

                # Track line-level records
                if row_data.get("EQUIPMENT_TYPE") == "LINE":
                    stats["line_level_records"] += 1
                # Also check if equipment name equals line name (common line-level identifier)
                elif (
                    row_data.get("EQUIPMENT_NAME")
                    and row_data.get("LINE_NAME")
                    and row_data.get("EQUIPMENT_NAME") == row_data.get("LINE_NAME")
                ):
                    stats["line_level_records"] += 1
                # Check for equipment type issues only for actual equipment records
                elif (
                    row_data.get("EQUIPMENT_NAME")
                    and row_data.get("LINE_NAME")
                    and row_data.get("EQUIPMENT_NAME") != row_data.get("LINE_NAME")
                ):
                    # Equipment with known type
                    if (
                        row_data.get("EQUIPMENT_BASE_TYPE")
                        and row_data.get("EQUIPMENT_BASE_TYPE") != "Unknown"
                    ):
                        stats["equipment_with_type"] += 1

                        # Track specific equipment types
                        equip_type = row_data.get("EQUIPMENT_BASE_TYPE")
                        if equip_type in equipment_type_counts:
                            equipment_type_counts[equip_type] += 1
                        else:
                            equipment_type_counts[equip_type] = 1
                    # Equipment with missing or unknown type
                    else:
                        stats["equipment_type_missing"] += 1

                # Process the row
                map_row_to_ontology(
                    row_data,
                    equipment_sequence_overrides,
                    equipment_type_sequence_order,
                )

                stats["processed_rows"] += 1

                # Log progress periodically
                if (i + 1) % 100 == 0 or i + 1 == row_count:
                    logger.info(
                        f"Processed {i + 1}/{row_count} rows ({(i + 1) / row_count:.1%})"
                    )

            except Exception as e:
                record_id = row_data.get("record_id_str", "N/A")
                logger.warning(f"Error processing row {record_id}: {e}")
                stats["error_rows"] += 1

        # Save ontology
        output_path = args.output
        logger.info(f"Saving ontology to {output_path}")
        onto.save(file=output_path, format="rdfxml")

        # Synchronize reasoner
        logger.info("Synchronizing reasoner")
        try:
            with onto:
                owl.sync_reasoner()
            logger.info("Reasoner synchronized successfully")
        except Exception as e:
            logger.warning(f"Could not synchronize reasoner: {e}")

        # Run example queries
        logger.info("Running example queries")
        case_packers = find_equipment_by_type("CasePacker")
        logger.info(f"Found {len(case_packers)} CasePacker equipment instances")

        # Log processing statistics
        logger.info("Processing statistics:")
        logger.info(
            f"  Total rows processed: {stats['processed_rows']}/{stats['total_rows']} ({stats['processed_rows']/stats['total_rows']:.1%})"
        )
        if stats["error_rows"] > 0:
            logger.info(
                f"  Rows with errors: {stats['error_rows']} ({stats['error_rows']/stats['total_rows']:.1%})"
            )

        # Report on time info with additional context
        if stats["missing_time_info"] > 0:
            missing_time_pct = stats["missing_time_info"] / stats["total_rows"]
            if missing_time_pct > 0.90:  # If more than 90% are missing
                logger.info(
                    f"  Rows with missing time info: {stats['missing_time_info']} ({missing_time_pct:.1%}) - This may be normal if your data uses event-specific time fields"
                )
            else:
                logger.info(
                    f"  Rows with missing time info: {stats['missing_time_info']} ({missing_time_pct:.1%})"
                )

        logger.info(
            f"  Line-level records: {stats['line_level_records']} ({stats['line_level_records']/stats['total_rows']:.1%})"
        )
        logger.info(
            f"  Equipment with known types: {stats['equipment_with_type']} ({stats['equipment_with_type']/stats['total_rows']:.1%})"
        )
        logger.info(
            f"  Equipment with missing types: {stats['equipment_type_missing']} ({stats['equipment_type_missing']/stats['total_rows']:.1%})"
        )

        # Report specific equipment types if any were found
        if equipment_type_counts:
            logger.info("  Equipment type distribution:")
            for equip_type, count in sorted(
                equipment_type_counts.items(), key=lambda x: x[1], reverse=True
            ):
                logger.info(f"    - {equip_type}: {count} instances")

        # Success
        logger.info("Processing completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Error in main process: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
