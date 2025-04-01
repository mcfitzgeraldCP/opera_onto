"""
Main module for the ontology generator.

This module provides the main entry point for the ontology generator.
"""
import argparse
import csv
import logging
import os
import sys
import time as timing
from datetime import datetime, date, time
from typing import List, Dict, Any, Optional, Tuple

from owlready2 import (
    World, Ontology, sync_reasoner, Thing,
    OwlReadyInconsistentOntologyError, locstr, default_world
)

from ontology_generator.config import DEFAULT_ONTOLOGY_IRI, init_xsd_type_map
from ontology_generator.utils.logging import (
    main_logger, configure_logging, analysis_logger
)
from ontology_generator.definition.parser import (
    parse_specification, parse_property_mappings, validate_property_mappings, read_data
)
from ontology_generator.definition.structure import (
    define_ontology_structure, create_selective_classes
)
from ontology_generator.population.core import get_or_create_individual
from ontology_generator.population.asset import (
    process_asset_hierarchy, process_material, process_production_request
)
from ontology_generator.population.equipment import process_equipment
from ontology_generator.population.events import (
    process_shift, process_state_reason, process_time_interval, process_event_record
)
from ontology_generator.population.sequence import (
    setup_equipment_sequence_relationships, setup_equipment_instance_relationships
)
from ontology_generator.population.linking import link_equipment_events_to_line_events
from ontology_generator.analysis.population import (
    analyze_ontology_population, generate_population_report, generate_optimization_recommendations
)
from ontology_generator.analysis.reasoning import generate_reasoning_report

# Initialize XSD type map and datetime types
init_xsd_type_map(locstr)

def populate_ontology_from_data(onto: Ontology,
                                data_rows: List[Dict[str, Any]],
                                defined_classes: Dict[str, object],
                                defined_properties: Dict[str, object],
                                property_is_functional: Dict[str, bool],
                                specification: List[Dict[str, str]],
                                property_mappings: Dict[str, Dict[str, Dict[str, Any]]] = None
                              ) -> Tuple[int, Dict[str, object], Dict[str, int], List[Tuple[object, object, object, object]]]:
    """
    Populates the ontology with individuals and relations from data rows.
    
    Args:
        onto: The ontology to populate
        data_rows: The data rows from the data CSV file
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        property_is_functional: Dictionary indicating functionality of properties
        specification: The parsed specification
        property_mappings: Optional property mappings dictionary
        
    Returns:
        tuple: (failed_rows_count, created_equipment_class_inds, equipment_class_positions, created_events_context)
    """
    from ontology_generator.population.core import PopulationContext
    
    main_logger.info(f"Starting ontology population with {len(data_rows)} data rows.")

    # Create population context
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)

    # Check essential classes
    essential_classes_names = [
        "Plant", "Area", "ProcessCell", "ProductionLine", "Equipment",
        "EquipmentClass", "Material", "ProductionRequest", "EventRecord",
        "TimeInterval", "Shift", "OperationalState", "OperationalReason"
    ]
    missing_classes = [name for name in essential_classes_names if not context.get_class(name)]
    if missing_classes:
        # get_class already logged errors, just return failure
        return len(data_rows), {}, {}, []  # Empty context

    # Check essential properties
    essential_prop_names = {
        "plantId", "areaId", "processCellId", "lineId", "equipmentId", "equipmentName",
        "locatedInPlant", "partOfArea", "locatedInProcessCell", "isPartOfProductionLine",
        "memberOfClass", "equipmentClassId", "defaultSequencePosition",
        "materialId", "materialDescription", "usesMaterial",
        "requestId", "requestDescription", "associatedWithProductionRequest",
        "shiftId", "shiftStartTime", "shiftEndTime", "shiftDurationMinutes", "duringShift",
        "stateDescription", "eventHasState",
        "reasonDescription", "altReasonDescription", "eventHasReason",
        "startTime", "endTime", "occursDuring",
        "involvesResource",  # Core link for EventRecord
        "classIsUpstreamOf", "classIsDownstreamOf",
        "equipmentIsUpstreamOf", "equipmentIsDownstreamOf",
        "isPartOfLineEvent", "startTime", "endTime"
    }
    missing_essential_props = [name for name in essential_prop_names if not context.get_prop(name)]
    if missing_essential_props:
        main_logger.error(f"Cannot reliably proceed. Missing essential properties definitions: {missing_essential_props}")
        return len(data_rows), {}, {}, []  # Empty context

    # Warn about other missing properties defined in spec but not found
    all_spec_prop_names = {row.get('Proposed OWL Property','').strip() for row in specification if row.get('Proposed OWL Property')}
    for spec_prop in all_spec_prop_names:
        if spec_prop and not context.get_prop(spec_prop):
            main_logger.warning(f"Property '{spec_prop}' (from spec) not found in defined_properties. Population using this property will be skipped.")

    # Track equipment class details across rows for sequencing
    created_equipment_class_inds = {}  # {eq_class_name_str: eq_class_ind_obj}
    equipment_class_positions = {}  # {eq_class_name_str: position_int}

    # Initialize storage for event linking context
    created_events_context = []  # List to store tuples: (event_ind, resource_ind, time_interval_ind, line_ind_associated)

    # Process data rows
    successful_rows = 0
    failed_rows = 0
    with onto:  # Use the ontology context for creating individuals
        for i, row in enumerate(data_rows):
            row_num = i + 2  # 1-based index + header row = line number in CSV
            main_logger.debug(f"--- Processing Row {row_num} ---")
            try:
                # 1. Process Asset Hierarchy -> plant, area, pcell, line individuals
                plant_ind, area_ind, pcell_ind, line_ind = process_asset_hierarchy(row, context, property_mappings)
                if not plant_ind:  # Plant is essential to continue processing this row meaningfully
                    raise ValueError("Failed to establish Plant individual, cannot proceed with row.")

                # 2. Determine Resource (Line or Equipment) for the Event
                eq_type = row.get('EQUIPMENT_TYPE', '')
                resource_individual = None
                resource_base_id = None  # For naming related individuals
                equipment_ind = None
                eq_class_ind = None
                eq_class_name = None

                if eq_type == 'Line' and line_ind:
                    resource_individual = line_ind
                    resource_base_id = line_ind.name  # Use unique IRI name
                    main_logger.debug(f"Row {row_num}: Identified as Line record for: {line_ind.name}")

                elif eq_type == 'Equipment':
                    # Process Equipment -> equipment, eq_class individuals
                    equipment_ind, eq_class_ind, eq_class_name = process_equipment(row, context, line_ind, property_mappings)
                    if equipment_ind:
                        resource_individual = equipment_ind
                        resource_base_id = f"Eq_{equipment_ind.name}"  # Prefix for clarity

                        # Track equipment class info if successfully created/retrieved
                        if eq_class_ind and eq_class_name:
                            if eq_class_name not in created_equipment_class_inds:
                                created_equipment_class_inds[eq_class_name] = eq_class_ind
                            # Update position map if a position is defined for the class
                            pos = getattr(eq_class_ind, "defaultSequencePosition", None)
                            if pos is not None:
                                # Check if existing stored pos is different (shouldn't happen with functional prop)
                                if eq_class_name in equipment_class_positions and equipment_class_positions[eq_class_name] != pos:
                                    main_logger.warning(f"Sequence position conflict for class '{eq_class_name}'. Existing: {equipment_class_positions[eq_class_name]}, New: {pos}. Using new value: {pos}")
                                equipment_class_positions[eq_class_name] = pos
                                main_logger.debug(f"Tracked position {pos} for class '{eq_class_name}'.")

                    else:
                         main_logger.warning(f"Row {row_num}: Identified as Equipment record, but failed to process Equipment individual. Event linkages might be incomplete.")
                         # Allow continuing, but event will link to nothing specific if eq failed

                else:
                    main_logger.warning(f"Row {row_num}: Could not determine resource. EQUIPMENT_TYPE='{eq_type}', EQUIPMENT_ID='{row.get('EQUIPMENT_ID')}', LINE_NAME='{row.get('LINE_NAME')}'. Event linkages might be incomplete.")
                    # Continue processing other parts of the row, but linkages will be affected

                # Check if a resource was identified for linking the event
                if not resource_individual:
                    main_logger.error(f"Row {row_num}: No valid resource (Line or Equipment) individual identified or created. Cannot link event record correctly.")
                    # Decide whether to skip the rest of the row or continue without linking event
                    # raise ValueError("Resource individual missing, cannot proceed with event linking.") # Stricter approach
                    # Let's continue but log the issue clearly. Event won't link to resource.
                    resource_base_id = f"UnknownResource_Row{row_num}" # Fallback for naming interval/event


                # 3. Process Material -> material individual
                material_ind = process_material(row, context, property_mappings)

                # 4. Process Production Request -> request individual
                request_ind = process_production_request(row, context, material_ind, property_mappings)

                # 5. Process Shift -> shift individual
                shift_ind = process_shift(row, context, property_mappings)

                # 6. Process State & Reason -> state, reason individuals
                state_ind, reason_ind = process_state_reason(row, context, property_mappings)

                # 7. Process Time Interval -> interval individual
                time_interval_ind = process_time_interval(row, context, resource_base_id, row_num, property_mappings)

                # 8. Process Event Record and Links -> event individual
                event_ind = None
                if resource_individual:  # Only process event if resource exists
                    event_ind = process_event_record(row, context, resource_individual, resource_base_id, row_num,
                                                     request_ind, material_ind, time_interval_ind,
                                                     shift_ind, state_ind, reason_ind, property_mappings)
                    if not event_ind:
                        # Error logged in process_event_record
                        raise ValueError("Failed to create EventRecord individual.")
                    else:
                        # Store context for event linking
                        associated_line_ind = None
                        if isinstance(resource_individual, context.get_class("ProductionLine")):
                            associated_line_ind = resource_individual
                        elif isinstance(resource_individual, context.get_class("Equipment")):
                            # Get the line(s) this equipment belongs to
                            part_of_prop = context.get_prop("isPartOfProductionLine")
                            if part_of_prop:
                                line_list = getattr(resource_individual, part_of_prop.python_name, [])
                                if line_list and isinstance(line_list, list) and len(line_list) > 0:
                                    associated_line_ind = line_list[0]  # Take the first line if multiple
                                elif line_list and not isinstance(line_list, list):  # Handle single value case
                                    associated_line_ind = line_list

                        if associated_line_ind and isinstance(associated_line_ind, context.get_class("ProductionLine")):
                            created_events_context.append((event_ind, resource_individual, time_interval_ind, associated_line_ind))
                            main_logger.debug(f"Row {row_num}: Stored context for Event {event_ind.name} (Resource: {resource_individual.name}, Line: {associated_line_ind.name})")
                        else:
                            main_logger.warning(f"Row {row_num}: Could not determine associated ProductionLine for Event {event_ind.name}. Skipping for isPartOfLineEvent linking.")

                else:
                    main_logger.warning(f"Row {row_num}: Skipping EventRecord creation as no valid resource individual was found.")


                successful_rows += 1

            except Exception as e:
                failed_rows += 1
                main_logger.error(f"Error processing data row {row_num}: {row if len(str(row)) < 500 else str(row)[:500] + '...'}")
                main_logger.exception("Exception details:")

    # Log summaries
    main_logger.info("--- Unique Equipment Classes Found/Created ---")
    if created_equipment_class_inds:
        sorted_class_names = sorted(created_equipment_class_inds.keys())
        main_logger.info(f"Total unique equipment classes: {len(sorted_class_names)}")
        for class_name in sorted_class_names:
            main_logger.info(f"  • {class_name} (Position: {equipment_class_positions.get(class_name, 'Not Set')})")
    else:
        main_logger.warning("No EquipmentClass individuals were created or tracked during population!")

    main_logger.info(f"Ontology population complete. Successfully processed {successful_rows} rows, failed to process {failed_rows} rows.")
    return failed_rows, created_equipment_class_inds, equipment_class_positions, created_events_context


def main_ontology_generation(spec_file_path: str,
                             data_file_path: str,
                             output_owl_path: str,
                             ontology_iri: str = DEFAULT_ONTOLOGY_IRI,
                             save_format: str = "rdfxml",
                             use_reasoner: bool = False,
                             world_db_path: Optional[str] = None,
                             reasoner_report_max_entities: int = 10,
                             reasoner_report_verbose: bool = False,
                             analyze_population: bool = True,
                             strict_adherence: bool = False,
                             skip_classes: List[str] = None,
                             optimize_ontology: bool = False
                            ) -> bool:
    """
    Main function to generate the ontology.
    
    Args:
        spec_file_path: Path to the specification CSV file
        data_file_path: Path to the data CSV file
        output_owl_path: Path to save the generated OWL ontology file
        ontology_iri: Base IRI for the ontology
        save_format: Format for saving the ontology
        use_reasoner: Whether to run the reasoner after population
        world_db_path: Path to use/create a persistent SQLite world database
        reasoner_report_max_entities: Maximum number of entities to show per category in the reasoner report
        reasoner_report_verbose: Whether to show all details in the reasoner report
        analyze_population: Whether to analyze and report on the ontology population
        strict_adherence: Whether to strictly adhere to the specification
        skip_classes: List of class names to skip
        optimize_ontology: Whether to generate optimization recommendations
        
    Returns:
        bool: True on success, False on failure
    """
    start_time = timing.time()
    main_logger.info("--- Starting Ontology Generation ---")
    main_logger.info(f"Specification file: {spec_file_path}")
    main_logger.info(f"Data file: {data_file_path}")
    main_logger.info(f"Output OWL file: {output_owl_path}")
    main_logger.info(f"Ontology IRI: {ontology_iri}")
    main_logger.info(f"Save format: {save_format}")
    main_logger.info(f"Run reasoner: {use_reasoner}")
    if world_db_path:
        main_logger.info(f"Using persistent world DB: {world_db_path}")
    main_logger.info(f"Reasoner report max entities: {reasoner_report_max_entities}")
    main_logger.info(f"Reasoner report verbose: {reasoner_report_verbose}")

    world = None  # Define world variable outside try block

    try:
        # 1. Parse Specification
        specification = parse_specification(spec_file_path)
        if not specification:
            main_logger.error("Specification parsing failed or resulted in empty spec. Aborting.")
            return False

        # 1.2 Parse Property Mappings from Specification
        property_mappings = parse_property_mappings(specification)
        main_logger.info(f"Parsed property mappings for {len(property_mappings)} entities from specification")
        
        # 1.3 Validate the Property Mappings
        validation_result = validate_property_mappings(property_mappings)
        if not validation_result:
            main_logger.warning("Property mapping validation had issues. Will continue but some properties may not be correctly populated.")
        else:
            main_logger.info("Property mapping validation passed successfully!")

        # 2. Create Ontology World and Ontology Object
        if world_db_path:
            main_logger.info(f"Initializing persistent World at: {world_db_path}")
            db_dir = os.path.dirname(world_db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                main_logger.info(f"Created directory for world DB: {db_dir}")
            world = World(filename=world_db_path)
            onto = world.get_ontology(ontology_iri).load()
            main_logger.info(f"Ontology object obtained from persistent world: {onto}")
        else:
            main_logger.info("Initializing in-memory World.")
            world = World()  # Create a fresh world
            onto = world.get_ontology(ontology_iri)
            main_logger.info(f"Ontology object created in memory: {onto}")

        # 3. Define Ontology Structure (TBox)
        if strict_adherence or skip_classes:
            main_logger.info("Using selective class creation with custom constraints")
            defined_classes = create_selective_classes(onto, specification, 
                                                      skip_classes=skip_classes, 
                                                      strict_adherence=strict_adherence)
            # Still need to define properties
            _, defined_properties, property_is_functional = define_ontology_structure(onto, specification)
        else:
            defined_classes, defined_properties, property_is_functional = define_ontology_structure(onto, specification)
            
        if not defined_classes:
            main_logger.warning("Ontology structure definition resulted in no classes. Population might be empty.")

        # 4. Read Operational Data
        data_rows = read_data(data_file_path)

        # 5. Populate Ontology (ABox - First Pass)
        population_successful = True
        failed_rows_count = 0
        created_eq_classes = {}
        eq_class_positions = {}
        created_events_context = []

        if not data_rows:
            main_logger.warning("No data rows read from data file. Ontology will be populated with structure only.")
        else:
            try:
                failed_rows_count, created_eq_classes, eq_class_positions, created_events_context = populate_ontology_from_data(
                    onto, data_rows, defined_classes, defined_properties, property_is_functional, 
                    specification, property_mappings
                )
                if failed_rows_count == len(data_rows) and len(data_rows) > 0:
                    main_logger.error(f"Population failed for all {len(data_rows)} data rows.")
                    population_successful = False
                elif failed_rows_count > 0:
                    main_logger.warning(f"Population completed with {failed_rows_count} out of {len(data_rows)} failed rows.")
                else:
                    main_logger.info(f"Population completed successfully for all {len(data_rows)} rows.")

            except Exception as pop_exc:
                main_logger.error(f"Critical error during population: {pop_exc}", exc_info=True)
                population_successful = False

        # --- Analyze Ontology Population ---
        if population_successful and analyze_population:
            main_logger.info("Analyzing ontology population status...")
            try:
                population_counts, empty_classes, class_instances, class_usage_info = analyze_ontology_population(onto, defined_classes, specification)
                population_report = generate_population_report(population_counts, empty_classes, class_instances, defined_classes, class_usage_info)
                main_logger.info("Ontology Population Analysis Complete")
                print(population_report)  # Print to console for immediate visibility
                
                # Generate optimization recommendations if requested
                if optimize_ontology:
                    main_logger.info("Generating detailed optimization recommendations...")
                    optimization_recs = generate_optimization_recommendations(class_usage_info, defined_classes)
                    
                    # Print the recommendations
                    print("\n=== DETAILED OPTIMIZATION RECOMMENDATIONS ===")
                    if optimization_recs.get('classes_to_remove'):
                        print(f"\nClasses that could be safely removed ({len(optimization_recs['classes_to_remove'])}):")
                        for class_name in optimization_recs['classes_to_remove']:
                            print(f"  • {class_name}")
                    
                    if optimization_recs.get('configuration_options'):
                        print("\nSuggested configuration for future runs:")
                        for option in optimization_recs['configuration_options']:
                            print(f"  • {option}")
                    
                    # Write recommendations to a file for later use
                    try:
                        base_dir = os.path.dirname(output_owl_path)
                        recs_file = os.path.join(base_dir, "ontology_optimization.txt")
                        with open(recs_file, 'w') as f:
                            f.write("# Ontology Optimization Recommendations\n\n")
                            f.write("## Classes to Remove\n")
                            for cls in optimization_recs.get('classes_to_remove', []):
                                f.write(f"- {cls}\n")
                            f.write("\n## Configuration Options\n")
                            for opt in optimization_recs.get('configuration_options', []):
                                f.write(f"- {opt}\n")
                        main_logger.info(f"Saved optimization recommendations to {recs_file}")
                    except Exception as e:
                        main_logger.error(f"Failed to save optimization recommendations: {e}")
                        
            except Exception as analysis_exc:
                main_logger.error(f"Error analyzing ontology population: {analysis_exc}", exc_info=False)
                # Continue with other processing despite analysis failure
        elif not analyze_population:
            main_logger.warning("Skipping ontology population analysis due to analyze_population flag.")

        # --- Setup Sequence Relationships AFTER population ---
        if population_successful and created_eq_classes and eq_class_positions:
            main_logger.info("Proceeding to setup sequence relationships...")
            try:
                setup_equipment_sequence_relationships(onto, eq_class_positions, defined_classes, defined_properties, created_eq_classes)
                setup_equipment_instance_relationships(onto, defined_classes, defined_properties, property_is_functional, eq_class_positions)
            except Exception as seq_exc:
                main_logger.error(f"Error during sequence relationship setup: {seq_exc}", exc_info=True)
                # Continue, but log error
        elif population_successful:
            main_logger.warning("Skipping sequence relationship setup because no EquipmentClass individuals or positions were generated/tracked during population.")
        else:
             main_logger.warning("Skipping sequence relationship setup due to population failure.")


        # --- Event Linking Pass ---
        if population_successful:  # Only link if population didn't fail critically
            main_logger.info("Proceeding to link equipment events to line events...")
            try:
                links_made = link_equipment_events_to_line_events(
                    onto, created_events_context, defined_classes, defined_properties
                )
                main_logger.info(f"Event linking pass created {links_made} links.")
            except Exception as link_exc:
                main_logger.error(f"Error during event linking pass: {link_exc}", exc_info=True)
                # Decide if this error should prevent saving or reasoning
                # For now, allow continuing but log the error clearly.
        else:
            main_logger.warning("Skipping event linking pass due to population failure.")


        # 6. Apply Reasoning (Optional)
        reasoning_successful = True
        if use_reasoner and population_successful:
            main_logger.info("Applying reasoner (ensure HermiT or compatible reasoner is installed)...")
            try:
                # Use the active world (persistent or default)
                active_world = world if world_db_path else default_world
                with onto:  # Use ontology context for reasoning
                    pre_stats = {
                        'classes': len(list(onto.classes())), 'object_properties': len(list(onto.object_properties())),
                        'data_properties': len(list(onto.data_properties())), 'individuals': len(list(onto.individuals()))
                    }
                    main_logger.info("Starting reasoning process...")
                    reasoning_start_time = timing.time()
                    # Run reasoner on the specific world containing the ontology
                    sync_reasoner(infer_property_values=True, debug=0)
                    reasoning_end_time = timing.time()
                    main_logger.info(f"Reasoning finished in {reasoning_end_time - reasoning_start_time:.2f} seconds.")

                    # Collect results from the correct world
                    inconsistent = list(active_world.inconsistent_classes())
                    inferred_hierarchy = {}
                    inferred_properties = {}
                    inferred_individuals = {}
                    
                    # Simplified post-reasoning state collection
                    for cls in onto.classes():
                        current_subclasses = set(cls.subclasses())
                        inferred_subs = [sub.name for sub in current_subclasses if sub != cls and sub != Nothing]  # Exclude self and Nothing
                        equivalent_classes = [eq.name for eq in cls.equivalent_to if eq != cls and isinstance(eq, ThingClass)]
                        if inferred_subs or equivalent_classes:
                            inferred_hierarchy[cls.name] = {'subclasses': inferred_subs, 'equivalent': equivalent_classes}

                    inferrable_chars = {
                        'FunctionalProperty': FunctionalProperty, 'InverseFunctionalProperty': InverseFunctionalProperty,
                        'TransitiveProperty': TransitiveProperty, 'SymmetricProperty': SymmetricProperty,
                        'AsymmetricProperty': AsymmetricProperty, 'ReflexiveProperty': ReflexiveProperty,
                        'IrreflexiveProperty': IrreflexiveProperty,
                    }
                    for prop in list(onto.object_properties()) + list(onto.data_properties()):
                        # Check direct types post-reasoning
                        inferred_chars_for_prop = [char_name for char_name, char_class in inferrable_chars.items() if char_class in prop.is_a]
                        if inferred_chars_for_prop: inferred_properties[prop.name] = inferred_chars_for_prop

                    main_logger.info("Collecting simplified individual inferences (post-reasoning state).")
                    for ind in onto.individuals():
                        # Get direct types post-reasoning
                        current_types = [c.name for c in ind.is_a if c is not Thing]
                        current_props = {}
                        # Check all properties for inferred values
                        for prop in list(onto.object_properties()) + list(onto.data_properties()):
                            try:
                                # Use direct property access post-reasoning
                                values = prop[ind]  # Gets inferred values
                                if not isinstance(values, list): values = [values] if values is not None else []

                                if values:
                                    formatted_values = []
                                    for v in values:
                                        if isinstance(v, Thing): formatted_values.append(v.name)
                                        elif isinstance(v, locstr): formatted_values.append(f'"{v}"@{v.lang}')
                                        else: formatted_values.append(repr(v))
                                    if formatted_values: current_props[prop.name] = formatted_values
                            except Exception: continue  # Ignore props not applicable or errors

                        if current_types or current_props:  # Only report if types or properties inferred/present
                            inferred_individuals[ind.name] = {'types': current_types, 'properties': current_props}


                    post_stats = {
                        'classes': len(list(onto.classes())), 'object_properties': len(list(onto.object_properties())),
                        'data_properties': len(list(onto.data_properties())), 'individuals': len(list(onto.individuals()))
                    }
                    report, has_issues = generate_reasoning_report(
                        onto, pre_stats, post_stats, inconsistent, inferred_hierarchy, 
                        inferred_properties, inferred_individuals, use_reasoner,
                        max_entities_per_category=reasoner_report_max_entities,
                        verbose=reasoner_report_verbose
                    )
                    main_logger.info("\nReasoning Report:\n" + report)

                    if has_issues or inconsistent:
                        main_logger.warning("Reasoning completed but potential issues or inconsistencies were identified.")
                        if inconsistent: reasoning_successful = False
                    else: main_logger.info("Reasoning completed successfully with no inconsistencies identified.")

            except OwlReadyInconsistentOntologyError:
                main_logger.error("REASONING FAILED: Ontology is inconsistent!")
                reasoning_successful = False
                try:
                    # Use the active world (persistent or default)
                    active_world = world if world_db_path else default_world
                    inconsistent = list(active_world.inconsistent_classes())
                    main_logger.error(f"Inconsistent classes detected: {[c.name for c in inconsistent]}")
                except Exception as e_inc: main_logger.error(f"Could not retrieve inconsistent classes: {e_inc}")
            except NameError as ne:
                if "sync_reasoner" in str(ne): main_logger.error("Reasoning failed: Reasoner (sync_reasoner) function not found. Is owlready2 installed correctly?")
                else: main_logger.error(f"Unexpected NameError during reasoning: {ne}")
                reasoning_successful = False
            except Exception as e:
                main_logger.error(f"An error occurred during reasoning: {e}", exc_info=True)
                reasoning_successful = False
        elif use_reasoner and not population_successful:
             main_logger.warning("Skipping reasoning due to population failure.")


        # 7. Save Ontology
        should_save_primary = population_successful and (not use_reasoner or reasoning_successful)
        final_output_path = output_owl_path
        save_attempted = False

        if not should_save_primary:
            main_logger.error("Ontology generation encountered errors (population or reasoning failure/inconsistency). Ontology will NOT be saved to the primary output file.")
            # Construct debug file path
            base, ext = os.path.splitext(output_owl_path)
            debug_output_path = f"{base}_debug{ext}"
            if debug_output_path == output_owl_path:  # Avoid overwriting if extension wasn't .owl or similar
                debug_output_path = output_owl_path + "_debug"

            main_logger.info(f"Attempting to save potentially problematic ontology to: {debug_output_path}")
            final_output_path = debug_output_path
            should_save_debug = True  # We always try to save the debug file if primary fails
        else:
            should_save_debug = False  # No need for debug file

        if should_save_primary or should_save_debug:
            main_logger.info(f"Saving ontology to {final_output_path} in '{save_format}' format...")
            save_attempted = True
            try:
                # Explicitly pass the world if using persistent storage
                if world_db_path:
                    onto.save(file=final_output_path, format=save_format, world=world)
                else:
                    onto.save(file=final_output_path, format=save_format)  # Use default world
                main_logger.info("Ontology saved successfully.")
            except Exception as save_err:
                main_logger.error(f"Failed to save ontology to {final_output_path}: {save_err}", exc_info=True)
                # If saving the primary failed, it's a failure. If saving debug failed, it's still a failure overall.
                return False

        # Determine overall success: Population must succeed, and if reasoning ran, it must succeed.
        # Saving must also have been attempted and not failed (implicit check via not returning False above).
        overall_success = population_successful and (not use_reasoner or reasoning_successful)

        return overall_success

    except Exception as e:
        main_logger.exception("A critical error occurred during the overall ontology generation process.")
        return False

    finally:
        end_time = timing.time()
        main_logger.info(f"--- Ontology Generation Finished ---")
        main_logger.info(f"Total time: {end_time - start_time:.2f} seconds")


def test_property_mappings(spec_file_path: str):
    """
    Test function to verify property mapping functionality.
    
    This can be called manually for testing and provides detailed debug output
    about the parsed property mappings for all entity types.
    
    Args:
        spec_file_path: Path to the specification CSV file
    """
    # Configure more verbose logging for testing
    configure_logging(level=logging.DEBUG)
    
    test_logger = logging.getLogger("property_mapping_test")
    test_logger.info("=== Starting Property Mapping Test ===")
    
    try:
        # Parse spec file
        test_logger.info(f"Parsing specification file: {spec_file_path}")
        spec = parse_specification(spec_file_path)
        test_logger.info(f"Parsed {len(spec)} rows from specification file")
        
        # Parse and validate property mappings
        test_logger.info("Generating property mappings from specification")
        mappings = parse_property_mappings(spec)
        validation_passed = validate_property_mappings(mappings)
        test_logger.info(f"Validation result: {'PASSED' if validation_passed else 'FAILED'}")
        
        # Group entities by logical group for organization
        from collections import defaultdict
        entity_groups = defaultdict(list)
        for row in spec:
            entity = row.get('Proposed OWL Entity', '').strip()
            group = row.get('Logical Group', '').strip()
            if entity and group:
                if entity not in entity_groups[group]:
                    entity_groups[group].append(entity)
                    
        # Print summary by group
        test_logger.info("\n=== Entity Coverage by Logical Group ===")
        for group, entities in sorted(entity_groups.items()):
            mapped_entities = [e for e in entities if e in mappings]
            test_logger.info(f"{group}: {len(mapped_entities)}/{len(entities)} entities mapped")
            
            if mapped_entities:
                for entity in sorted(mapped_entities):
                    data_props = len(mappings[entity].get('data_properties', {}))
                    obj_props = len(mappings[entity].get('object_properties', {}))
                    test_logger.info(f"  ✓ {entity}: {data_props} data properties, {obj_props} object properties")
            
            missing = [e for e in entities if e not in mappings]
            if missing:
                for entity in sorted(missing):
                    test_logger.warning(f"  ✗ {entity}: No property mappings found")
        
        # Detailed analysis of common entities
        key_entities = [
            'EventRecord', 
            'Material', 
            'OperationalReason', 
            'OperationalState',
            'ProductionLine',
            'Equipment',
            'EquipmentClass',
            'Plant',
            'Area',
            'ProcessCell',
            'Shift',
            'TimeInterval',
            'ProductionRequest'
        ]
        
        for entity in key_entities:
            if entity in mappings:
                entity_map = mappings[entity]
                
                test_logger.info(f"\n=== {entity} Property Mappings ===")
                
                # Data properties
                data_props = entity_map.get('data_properties', {})
                test_logger.info(f"Found {len(data_props)} data properties for {entity}")
                
                if data_props:
                    for prop_name, details in sorted(data_props.items()):
                        test_logger.info(f"  ✓ {prop_name}: column='{details.get('column')}', type='{details.get('data_type')}', functional={details.get('functional')}")
                
                # Object properties
                obj_props = entity_map.get('object_properties', {})
                if obj_props:
                    test_logger.info(f"Found {len(obj_props)} object properties for {entity}")
                    for prop_name, details in sorted(obj_props.items()):
                        test_logger.info(f"  ✓ {prop_name}: column='{details.get('column')}', target='{details.get('target_class')}', functional={details.get('functional')}")
            else:
                test_logger.warning(f"\n=== {entity} Property Mappings ===")
                test_logger.warning(f"  ✗ {entity} entity not found in mappings!")
        
        # Summary stats        
        total_data_props = sum(len(entity_map.get('data_properties', {})) for entity_map in mappings.values())
        total_obj_props = sum(len(entity_map.get('object_properties', {})) for entity_map in mappings.values())
        
        test_logger.info("\n=== Property Mapping Summary ===")
        test_logger.info(f"Total entities mapped: {len(mappings)}")
        test_logger.info(f"Total data properties mapped: {total_data_props}")
        test_logger.info(f"Total object properties mapped: {total_obj_props}")
        test_logger.info(f"Total properties mapped: {total_data_props + total_obj_props}")
        
        test_logger.info("=== Property Mapping Test Complete ===")
        
    except Exception as e:
        test_logger.error(f"Error during property mapping test: {e}", exc_info=True)


def main():
    """Main entry point for the ontology generator."""
    parser = argparse.ArgumentParser(description="Generate an OWL ontology from specification and data CSV files.")
    parser.add_argument("spec_file", help="Path to the ontology specification CSV file (e.g., opera_spec.csv).")
    parser.add_argument("data_file", help="Path to the operational data CSV file (e.g., sample_data.csv).")
    parser.add_argument("output_file", help="Path to save the generated OWL ontology file (e.g., manufacturing.owl).")
    parser.add_argument("--iri", default=DEFAULT_ONTOLOGY_IRI, help=f"Base IRI for the ontology (default: {DEFAULT_ONTOLOGY_IRI}).")
    parser.add_argument("--format", default="rdfxml", choices=["rdfxml", "ntriples", "nquads", "owlxml"], help="Format for saving the ontology (default: rdfxml).")
    parser.add_argument("--reasoner", action="store_true", help="Run the reasoner after population.")
    parser.add_argument("--worlddb", default=None, help="Path to use/create a persistent SQLite world database (e.g., my_ontology.sqlite3).")
    parser.add_argument("--max-report-entities", type=int, default=10, help="Maximum number of entities to show per category in the reasoner report (default: 10).")
    parser.add_argument("--full-report", action="store_true", help="Show full details in the reasoner report (all entities).")
    parser.add_argument("--no-analyze-population", action="store_false", dest="analyze_population", help="Skip analysis and reporting of ontology population (analysis is on by default).")
    parser.add_argument("--strict-adherence", action="store_true", help="Only create classes explicitly defined in the specification.")
    parser.add_argument("--skip-classes", type=str, nargs='+', help="List of class names to skip during ontology creation.")
    parser.add_argument("--optimize", action="store_true", dest="optimize_ontology", help="Generate detailed optimization recommendations.")
    parser.add_argument("--test-mappings", action="store_true", help="Test the property mapping functionality only, without generating the ontology.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO level logging.")

    args = parser.parse_args()

    # If test mode is requested, just run the test and exit
    if hasattr(args, 'test_mappings') and args.test_mappings:
        test_property_mappings(args.spec_file)
        sys.exit(0)

    # Setup Logging Level
    log_level = logging.INFO
    if args.verbose: 
        log_level = logging.DEBUG
    elif args.quiet: 
        log_level = logging.WARNING

    # Configure logging
    configure_logging(log_level=log_level)

    # Execute main function
    success = main_ontology_generation(
        args.spec_file, args.data_file, args.output_file,
        args.iri, args.format, args.reasoner, args.worlddb,
        reasoner_report_max_entities=args.max_report_entities,
        reasoner_report_verbose=args.full_report,
        analyze_population=args.analyze_population,
        strict_adherence=args.strict_adherence,
        skip_classes=args.skip_classes,
        optimize_ontology=args.optimize_ontology
    )

    # Exit with appropriate code
    if success:
        main_logger.info("Ontology generation process completed.")
        sys.exit(0)
    else:
        main_logger.error("Ontology generation process failed or encountered errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
