# create_ontology.py
# -*- coding: utf-8 -*-
"""
Main script to create and populate the manufacturing ontology.

Reads an ontology specification CSV and operational data CSV,
then generates an OWL file using owlready2.
"""

import argparse
import logging
import sys
import time
from owlready2 import *

# Import custom modules
from ontology_definition import parse_specification, define_ontology_structure
from ontology_population import populate_ontology_from_data, parse_equipment_class, safe_cast # Import helpers if needed directly

# --- Configuration ---
# Set default IRI, can be overridden
DEFAULT_ONTOLOGY_IRI = "http://example.com/manufacturing_ontology.owl"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

# Setup logging
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def read_data(data_file_path):
    """Reads the operational data CSV file."""
    logger.info(f"Reading data file: {data_file_path}")
    data_rows = []
    try:
        with open(data_file_path, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                data_rows.append(row)
        logger.info(f"Successfully read {len(data_rows)} data rows.")
        return data_rows
    except FileNotFoundError:
        logger.error(f"Data file not found: {data_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading data file {data_file_path}: {e}")
        raise


def main(spec_file_path, data_file_path, output_owl_path, ontology_iri=DEFAULT_ONTOLOGY_IRI):
    """
    Main function to generate the ontology.

    Args:
        spec_file_path (str): Path to the ontology specification CSV file.
        data_file_path (str): Path to the operational data CSV file.
        output_owl_path (str): Path to save the generated OWL file.
        ontology_iri (str): Base IRI for the new ontology.
    """
    start_time = time.time()
    logger.info("--- Starting Ontology Generation ---")
    logger.info(f"Specification file: {spec_file_path}")
    logger.info(f"Data file: {data_file_path}")
    logger.info(f"Output OWL file: {output_owl_path}")
    logger.info(f"Ontology IRI: {ontology_iri}")

    try:
        # 1. Parse Specification
        specification = parse_specification(spec_file_path)

        # 2. Create Ontology World and Ontology Object
        # For large datasets, consider using a file backend for the world:
        # world = World(filename="manufacturing_ontology.sqlite3")
        # onto = world.get_ontology(ontology_iri)
        # For this example, using default in-memory world:
        world = default_world
        onto = world.get_ontology(ontology_iri)

        # 3. Define Ontology Structure (TBox)
        defined_classes, defined_properties = define_ontology_structure(onto, specification)

        # 4. Read Operational Data
        data_rows = read_data(data_file_path)

        # 5. Populate Ontology (ABox)
        # IMPORTANT: Passing defined_classes and defined_properties helps avoid repeated lookups
        populate_ontology_from_data(onto, data_rows, defined_classes, defined_properties)

        # 6. Apply Reasoning (Optional - depends on analytics objective)
        # logger.info("Applying reasoner (HermiT)...")
        # try:
        #     sync_reasoner(infer_property_values=True) # Infer property values if needed
        #     logger.info("Reasoning complete.")
        # except OwlReadyInconsistentOntologyError:
        #     logger.error("Ontology is inconsistent according to the reasoner!")
        #     # Optionally check inconsistent classes:
        #     # inconsistent = list(world.inconsistent_classes())
        #     # logger.error(f"Inconsistent classes: {inconsistent}")
        # except Exception as e:
        #      logger.error(f"Error during reasoning: {e}")

        # 7. Save Ontology
        logger.info(f"Saving ontology to {output_owl_path} in RDF/XML format...")
        onto.save(file=output_owl_path, format="rdfxml")
        logger.info("Ontology saved successfully.")

    except Exception as e:
        logger.exception("An error occurred during ontology generation.")
        sys.exit(1) # Exit with error code

    end_time = time.time()
    logger.info(f"--- Ontology Generation Finished ---")
    logger.info(f"Total time: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an OWL ontology from specification and data CSV files.")
    parser.add_argument("spec_file", help="Path to the ontology specification CSV file (e.g., OPERA_ISA95_OWL_ONT_RICH.csv).")
    parser.add_argument("data_file", help="Path to the operational data CSV file (e.g., sample_data.csv).")
    parser.add_argument("output_file", help="Path to save the generated OWL ontology file (e.g., manufacturing.owl).")
    parser.add_argument("--iri", default=DEFAULT_ONTOLOGY_IRI, help=f"Base IRI for the ontology (default: {DEFAULT_ONTOLOGY_IRI}).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging.")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG) # Set root logger level
        for handler in logging.getLogger().handlers:
              handler.setLevel(logging.DEBUG)
        logger.info("Verbose logging enabled.")

    # Execute main function
    main(args.spec_file, args.data_file, args.output_file, args.iri)