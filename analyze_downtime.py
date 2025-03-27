#!/usr/bin/env python3
"""
Manufacturing Downtime Analysis

This script loads the Plant Owl ontology and uses SPARQL queries to find:
1. The line with the most total downtime
2. The piece of equipment on that line with the most downtime
"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd
import owlready2 as owl
from typing import Dict, List, Tuple, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Manufacturing Downtime Analysis")
    parser.add_argument(
        "--ontology-file", "-o", required=True, help="Path to the OWL ontology file"
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    return parser.parse_args()


def load_ontology(file_path: str) -> owl.Ontology:
    """Load the ontology from a file.

    Args:
        file_path: Path to the OWL ontology file

    Returns:
        The loaded ontology

    Raises:
        FileNotFoundError: If the ontology file cannot be found
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Ontology file not found: {path}")

    logger.info(f"Loading ontology from {path}")
    world = owl.World()
    ontology = world.get_ontology(path.absolute().as_uri()).load()

    # Basic stats about the loaded ontology
    equipment_count = len(list(ontology.Equipment.instances()))
    line_count = len(list(ontology.Line.instances()))
    event_count = len(list(ontology.EventRecord.instances()))

    logger.info(f"Loaded ontology with:")
    logger.info(f"  - {line_count} lines")
    logger.info(f"  - {equipment_count} equipment instances")
    logger.info(f"  - {event_count} event records")

    return ontology


def find_line_with_most_downtime(onto: owl.Ontology) -> Tuple[Any, float]:
    """Find the line with the most total downtime.

    Args:
        onto: The loaded ontology

    Returns:
        Tuple containing (line instance, total downtime in seconds)
    """
    logger.info("Finding line with the most downtime...")

    # Use SPARQL to query the ontology
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX onto: <http://example.org/manufacturing_revised_ontology.owl#>
    
    SELECT ?line (SUM(?duration) AS ?total_downtime)
    WHERE {
        ?event rdf:type onto:EventRecord .
        ?event onto:occursOnLine ?line .
        ?event onto:hasState ?state .
        ?state rdf:type onto:DowntimeState .
        ?event onto:stateDuration ?duration .
    }
    GROUP BY ?line
    ORDER BY DESC(?total_downtime)
    LIMIT 1
    """

    # Execute the query
    results = list(onto.world.sparql(query))

    if not results:
        logger.warning("No downtime events found in the ontology")
        return None, 0

    line, total_downtime = results[0]
    line_name = (
        line.lineName[0] if hasattr(line, "lineName") and line.lineName else "Unknown"
    )

    logger.info(f"Line with most downtime: {line_name} ({total_downtime:.2f} seconds)")
    return line, total_downtime


def find_equipment_with_most_downtime(
    onto: owl.Ontology, line: Any
) -> Tuple[Any, float]:
    """Find the equipment on a specific line with the most downtime.

    Args:
        onto: The loaded ontology
        line: The line instance to analyze

    Returns:
        Tuple containing (equipment instance, total downtime in seconds)
    """
    line_name = (
        line.lineName[0] if hasattr(line, "lineName") and line.lineName else "Unknown"
    )
    logger.info(f"Finding equipment with most downtime on line {line_name}...")

    # Log the IRI of the line
    logger.debug(f"Line IRI: {line.iri}")

    # Verify ontology loading
    if not onto:
        logger.error("Ontology is not loaded correctly.")
        return None, 0

    if not line:
        logger.error("Line instance is not valid.")
        return None, 0

    # Use SPARQL to query the ontology
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX onto: <http://example.org/manufacturing_revised_ontology.owl#>
    
    SELECT ?equipment (SUM(?duration) AS ?total_downtime)
    WHERE {{
        ?event rdf:type onto:EventRecord .
        ?event onto:occursOnLine ?line .
        ?event onto:involvesEquipment ?equipment .
        ?event onto:hasState ?state .
        ?state rdf:type onto:DowntimeState .
        ?event onto:stateDuration ?duration .
        
        FILTER(?line = <{line.iri}>)
    }}
    GROUP BY ?equipment
    ORDER BY DESC(?total_downtime)
    LIMIT 1
    """

    # Execute the query
    results = list(onto.world.sparql(query))

    if not results:
        logger.warning(f"No equipment downtime events found for line {line_name}")
        return None, 0

    equipment, total_downtime = results[0]

    equipment_name = (
        equipment.equipmentName[0]
        if hasattr(equipment, "equipmentName") and equipment.equipmentName
        else "Unknown"
    )
    equipment_type = (
        equipment.equipmentBaseType[0]
        if hasattr(equipment, "equipmentBaseType") and equipment.equipmentBaseType
        else "Unknown"
    )

    logger.info(
        f"Equipment with most downtime: {equipment_name} (Type: {equipment_type}, Downtime: {total_downtime:.2f} seconds)"
    )
    return equipment, total_downtime


def analyze_downtime_reasons(
    onto: owl.Ontology, equipment: Any
) -> List[Tuple[str, float]]:
    """Analyze downtime reasons for a specific piece of equipment.

    Args:
        onto: The loaded ontology
        equipment: The equipment instance to analyze

    Returns:
        List of tuples containing (reason description, total duration)
    """
    equipment_name = (
        equipment.equipmentName[0]
        if hasattr(equipment, "equipmentName") and equipment.equipmentName
        else "Unknown"
    )
    logger.info(f"Analyzing downtime reasons for {equipment_name}...")

    # Use SPARQL to query the ontology
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX onto: <http://example.org/manufacturing_revised_ontology.owl#>
    
    SELECT ?reason_description (SUM(?duration) AS ?total_duration)
    WHERE {
        ?event rdf:type onto:EventRecord .
        ?event onto:involvesEquipment ?equipment .
        ?event onto:hasState ?state .
        ?state rdf:type onto:DowntimeState .
        ?event onto:hasReason ?reason .
        ?reason onto:reasonDescription ?reason_description .
        ?event onto:stateDuration ?duration .
        
        FILTER(?equipment = ?target_equipment)
    }
    GROUP BY ?reason_description
    ORDER BY DESC(?total_duration)
    """

    # Execute the query with binding for the target equipment
    results = list(onto.world.sparql(query, [equipment]))

    if not results:
        logger.warning(f"No downtime reasons found for equipment {equipment_name}")
        return []

    # Convert results to a more usable format
    reason_durations = [(str(reason), float(duration)) for reason, duration in results]

    # Print the top 5 reasons
    logger.info(f"Top downtime reasons for {equipment_name}:")
    for i, (reason, duration) in enumerate(reason_durations[:5], 1):
        logger.info(f"  {i}. {reason}: {duration:.2f} seconds")

    return reason_durations


def main():
    """Main application entry point."""
    # Parse arguments
    args = parse_arguments()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    try:
        # Load the ontology
        onto = load_ontology(args.ontology_file)

        # Find the line with the most downtime
        line, line_downtime = find_line_with_most_downtime(onto)
        if not line:
            logger.error("Could not find a line with downtime events")
            return 1

        # Find the equipment with the most downtime on that line
        equipment, equipment_downtime = find_equipment_with_most_downtime(onto, line)
        if not equipment:
            logger.error(
                f"Could not find equipment with downtime events on the identified line"
            )
            return 1

        # Analyze downtime reasons for the identified equipment
        reasons = analyze_downtime_reasons(onto, equipment)

        # Print summary
        line_name = (
            line.lineName[0]
            if hasattr(line, "lineName") and line.lineName
            else "Unknown"
        )
        equipment_name = (
            equipment.equipmentName[0]
            if hasattr(equipment, "equipmentName") and equipment.equipmentName
            else "Unknown"
        )
        equipment_type = (
            equipment.equipmentBaseType[0]
            if hasattr(equipment, "equipmentBaseType") and equipment.equipmentBaseType
            else "Unknown"
        )

        logger.info("\nDowntime Analysis Summary:")
        logger.info(
            f"Line with most downtime: {line_name} with {line_downtime:.2f} seconds"
        )
        logger.info(
            f"Equipment with most downtime on line {line_name}: {equipment_name} ({equipment_type}) with {equipment_downtime:.2f} seconds"
        )

        # Success
        return 0

    except Exception as e:
        logger.error(f"Error in analysis: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
