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
    OwlReadyInconsistentOntologyError, locstr, default_world,
    ThingClass, FunctionalProperty, InverseFunctionalProperty, TransitiveProperty, SymmetricProperty, AsymmetricProperty, ReflexiveProperty, IrreflexiveProperty, Nothing
)

from ontology_generator.config import (
    DEFAULT_ONTOLOGY_IRI, init_xsd_type_map, DEFAULT_EQUIPMENT_SEQUENCE,
    DEFAULT_EVENT_LINKING_BUFFER_MINUTES, DEFAULT_EVENT_DURATION_HOURS
)
from ontology_generator.utils.logging import (
    main_logger, configure_logging, analysis_logger
)
from ontology_generator.definition import (
    parse_specification, define_ontology_structure, create_selective_classes,
    parse_property_mappings, validate_property_mappings, read_data
)
from ontology_generator.population import (
    setup_equipment_instance_relationships,
    link_equipment_events_to_line_events
)
from ontology_generator.analysis import (
    analyze_ontology_population, generate_population_report,
    generate_optimization_recommendations, generate_reasoning_report,
    generate_equipment_sequence_report, analyze_equipment_sequences
)
from ontology_generator.utils import safe_cast # Import directly from utils now

# Initialize XSD type map and datetime types
init_xsd_type_map(locstr)

def populate_ontology_from_data(onto: Ontology,
                                data_rows: List[Dict[str, Any]],
                                defined_classes: Dict[str, object],
                                defined_properties: Dict[str, object],
                                property_is_functional: Dict[str, bool],
                                specification: List[Dict[str, str]],
                                property_mappings: Dict[str, Dict[str, Dict[str, Any]]] = None
                              ) -> Tuple[int, Dict[str, object], Dict[str, int], List[Tuple[object, object, object, object]], Dict]:
    """
    Populates the ontology with individuals and relations from data rows using a two-pass approach.
    Pass 1: Creates individuals and sets data properties.
    Pass 2: Creates object property relationships between individuals.

    Args:
        onto: The ontology to populate
        data_rows: The data rows from the data CSV file
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        property_is_functional: Dictionary indicating functionality of properties
        specification: The parsed specification
        property_mappings: Optional property mappings dictionary
        
    Returns:
        tuple: (failed_rows_count, created_equipment_class_inds, equipment_class_positions, created_events_context, all_created_individuals_by_uid)
    """
    # Ensure imports required *within* this function are present
    from ontology_generator.population.core import PopulationContext
    from ontology_generator.population.row_processor import process_single_data_row_pass1, process_single_data_row_pass2 # Import needed here

    main_logger.info(f"Starting ontology population with {len(data_rows)} data rows (Two-Pass Strategy).")

    # Create population context
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)

    # --- Pre-checks (Essential Classes and Properties) ---
    essential_classes_names = [
        "Plant", "Area", "ProcessCell", "ProductionLine", "Equipment",
        "EquipmentClass", "Material", "ProductionRequest", "EventRecord",
        "TimeInterval", "Shift", "OperationalState", "OperationalReason"
    ]
    missing_classes = [name for name in essential_classes_names if not context.get_class(name)]
    if missing_classes:
        # get_class already logged errors, just return failure
        main_logger.error(f"Cannot proceed. Missing essential classes definitions: {missing_classes}")
        return len(data_rows), {}, {}, [], {}  # Empty context

    essential_prop_names = { # Focus on IDs and core structure for initial checks
        "plantId", "areaId", "processCellId", "lineId", "equipmentId", "equipmentName",
        "equipmentClassId", "materialId", "requestId", "shiftId", "startTime", "endTime"
        # Object properties checked implicitly later
    }
    missing_essential_props = [name for name in essential_prop_names if not context.get_prop(name)]
    if missing_essential_props:
        main_logger.error(f"Cannot reliably proceed. Missing essential data properties definitions: {missing_essential_props}")
        return len(data_rows), {}, {}, [], {}  # Empty context

    # Warn about other missing properties defined in spec but not found
    all_spec_prop_names = {row.get('Proposed OWL Property','').strip() for row in specification if row.get('Proposed OWL Property')}
    for spec_prop in all_spec_prop_names:
        if spec_prop and not context.get_prop(spec_prop):
            main_logger.warning(f"Property '{spec_prop}' (from spec) not found in defined_properties. Population using this property will be skipped.")

    # --- Pass 1: Create Individuals and Apply Data Properties ---
    main_logger.info("--- Population Pass 1: Creating Individuals and Data Properties ---")
    all_created_individuals_by_uid = {} # {(entity_type, unique_id): individual_obj}
    individuals_by_row = {} # {row_index: {entity_type: individual_obj, ...}}
    created_equipment_class_inds = {}  # {eq_class_name_str: eq_class_ind_obj}
    equipment_class_positions = {}  # {eq_class_name_str: position_int}
    created_events_context = []  # List to store tuples for later linking: (event_ind, resource_ind, resource_type)
    pass1_successful_rows = 0
    pass1_failed_rows = 0

    with onto:  # Use the ontology context for creating individuals
        for i, row in enumerate(data_rows):
            row_num = i + 2  # 1-based index + header row = line number in CSV

            # Call the dedicated row processing function for Pass 1
            success, created_inds_in_row, event_context, eq_class_info = process_single_data_row_pass1(
                row, row_num, context, property_mappings, all_created_individuals_by_uid # Pass registry for get_or_create logic
            )

            if success:
                pass1_successful_rows += 1
                individuals_by_row[i] = created_inds_in_row # Store individuals created from this row
                # Update the global registry (used by get_or_create and Pass 2 context)
                # Note: process_single_data_row_pass1 should already populate all_created_individuals_by_uid via get_or_create calls
                
                # Store event context if returned
                if event_context:
                    created_events_context.append(event_context)

                # Process equipment class info if returned
                if eq_class_info:
                    eq_class_name, eq_class_ind, eq_class_pos = eq_class_info
                    if eq_class_name not in created_equipment_class_inds:
                        created_equipment_class_inds[eq_class_name] = eq_class_ind
                    # Update position map if a position is defined and potentially different
                    if eq_class_pos is not None:
                        if eq_class_name in equipment_class_positions and equipment_class_positions[eq_class_name] != eq_class_pos:
                             main_logger.warning(f"Sequence position conflict for class '{eq_class_name}' during population. Existing: {equipment_class_positions[eq_class_name]}, New: {eq_class_pos}. Using new value: {eq_class_pos}")
                        equipment_class_positions[eq_class_name] = eq_class_pos
                        # main_logger.debug(f"Tracked position {eq_class_pos} for class '{eq_class_name}'.") # Can be noisy

            else:
                pass1_failed_rows += 1
                individuals_by_row[i] = {} # Ensure entry exists even if row failed
                # Error logging handled within process_single_data_row_pass1

    main_logger.info(f"Pass 1 Complete. Successful rows: {pass1_successful_rows}, Failed rows: {pass1_failed_rows}.")
    main_logger.info(f"Total unique individuals created (approx): {len(all_created_individuals_by_uid)}")

    # Log Equipment Class Summary (collected during pass 1)
    main_logger.info("--- Unique Equipment Classes Found/Created (Pass 1) ---")
    if created_equipment_class_inds:
        sorted_class_names = sorted(created_equipment_class_inds.keys())
        main_logger.info(f"Total unique equipment classes: {len(sorted_class_names)}")
        for class_name in sorted_class_names:
            main_logger.info(f"  • {class_name} (Position: {equipment_class_positions.get(class_name, 'Not Set')})")
        
        # Log information about default sequence positions from config
        defaults_used = [name for name in sorted_class_names if name in DEFAULT_EQUIPMENT_SEQUENCE]
        if defaults_used:
            main_logger.info(f"Using default sequence positions from config for {len(defaults_used)} equipment classes: {', '.join(defaults_used)}")
    else:
        main_logger.warning("No EquipmentClass individuals were created or tracked during population!")

    # --- Pass 2: Apply Object Property Mappings ---
    main_logger.info("--- Population Pass 2: Linking Individuals (Object Properties) ---")
    pass2_successful_rows = 0
    pass2_failed_rows = 0
    # Prepare the full context dictionary for linking (use the values from the UID map)
    full_context_individuals = {k[0]: v for k, v in all_created_individuals_by_uid.items()} # Simple context {type_name: ind_obj} - May need refinement based on linking needs
    main_logger.info(f"Prepared context for Pass 2 with {len(full_context_individuals)} potential link targets.")


    # Refine context based on actual needs - Needs careful thought on how apply_object_property_mappings uses context_individuals
    # The warning "Context entity 'Equipment' required for Equipment.isParallelWith not found in provided context_individuals dictionary"
    # suggests the key should be the *type* ('Equipment') and the value the *target* individual.
    # However, apply_property_mappings seems to look up `context_individuals[link_context_entity]`.
    # For linking Equipment to Equipment via 'isParallelWith', link_context_entity would be 'Equipment'.
    # The current `apply_property_mappings` expects ONE individual for that key. This is flawed for many-to-many or one-to-many via context.

    # Let's assume apply_object_property_mappings will handle lookup within all_created_individuals_by_uid.
    # We pass the full registry instead of a simplified context.
    linking_context = all_created_individuals_by_uid

    with onto: # Context manager might not be strictly needed here if only setting properties
        for i, row in enumerate(data_rows):
            row_num = i + 2
            # Skip rows that failed significantly in Pass 1 (e.g., couldn't create core individuals)
            if i not in individuals_by_row or not individuals_by_row[i]:
                 main_logger.debug(f"Skipping Pass 2 linking for row {row_num} as no individuals were successfully created in Pass 1.")
                 pass2_failed_rows += 1 # Count as failed for Pass 2
                 continue

            created_inds_this_row = individuals_by_row[i]

            # Call the dedicated row processing function for Pass 2
            success = process_single_data_row_pass2(
                row, row_num, context, property_mappings, created_inds_this_row, linking_context
            )

            if success:
                pass2_successful_rows += 1
            else:
                pass2_failed_rows += 1
                # Logging handled within process_single_data_row_pass2

    main_logger.info(f"Pass 2 Complete. Rows successfully linked: {pass2_successful_rows}, Rows failed/skipped linking: {pass2_failed_rows}.")

    # Determine overall failed count - TKT-006: Improve failure reporting
    final_failed_rows = pass1_failed_rows  # Use the Pass 1 failures as the primary metric

    # Report both pass failures if they differ significantly
    if pass2_failed_rows > pass1_failed_rows:
        main_logger.warning(f"Note: Pass 2 had {pass2_failed_rows - pass1_failed_rows} additional failures during linking phase.")
    
    if final_failed_rows > 0:
        failure_rate = (final_failed_rows / len(data_rows)) * 100
        main_logger.info(f"Ontology population complete with {final_failed_rows} failed rows ({failure_rate:.1f}% failure rate).")
    else:
        main_logger.info("Ontology population complete. All rows processed successfully.")
        
    # Return collected contexts from Pass 1 and the registry
    return final_failed_rows, created_equipment_class_inds, equipment_class_positions, created_events_context, all_created_individuals_by_uid


def _log_initial_parameters(args, logger):
    logger.info("--- Starting Ontology Generation ---")
    logger.info(f"Specification file: {args.spec_file}")
    logger.info(f"Data file: {args.data_file}")
    logger.info(f"Output OWL file: {args.output_file}")
    logger.info(f"Ontology IRI: {args.iri}")
    logger.info(f"Save format: {args.format}")
    logger.info(f"Run reasoner: {args.reasoner}")
    if args.worlddb:
        logger.info(f"Using persistent world DB: {args.worlddb}")
    logger.info(f"Reasoner report max entities: {args.max_report_entities}")
    logger.info(f"Reasoner report verbose: {args.full_report}")
    logger.info(f"Analyze population: {args.analyze_population}")
    logger.info(f"Strict adherence: {args.strict_adherence}")
    logger.info(f"Skip classes: {args.skip_classes}")
    logger.info(f"Optimize ontology: {args.optimize_ontology}")

def _parse_spec_and_mappings(spec_file_path, logger):
    logger.info(f"Parsing specification file: {spec_file_path}")
    specification = parse_specification(spec_file_path)
    if not specification:
        logger.error("Specification parsing failed or resulted in empty spec. Aborting.")
        return None, None # Indicate failure

    logger.info("Parsing property mappings from specification...")
    property_mappings = parse_property_mappings(specification)
    logger.info(f"Parsed property mappings for {len(property_mappings)} entities")

    logger.info("Validating property mappings...")
    validation_result = validate_property_mappings(property_mappings)
    if not validation_result:
        logger.warning("Property mapping validation had issues. Population may be incomplete.")
    else:
        logger.info("Property mapping validation passed.")
    return specification, property_mappings

def _setup_world_and_ontology(ontology_iri, world_db_path, logger):
    world = None
    onto = None
    if world_db_path:
        logger.info(f"Initializing persistent World at: {world_db_path}")
        db_dir = os.path.dirname(world_db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created directory for world DB: {db_dir}")
            except OSError as e:
                 logger.error(f"Failed to create directory for world DB {db_dir}: {e}")
                 return None, None # Indicate failure
        try:
            world = World(filename=world_db_path)
            onto = world.get_ontology(ontology_iri).load()
            logger.info(f"Ontology object obtained from persistent world: {onto}")
        except Exception as db_err:
             logger.error(f"Failed to initialize or load from persistent world DB {world_db_path}: {db_err}", exc_info=True)
             return None, None # Indicate failure
    else:
        logger.info("Initializing in-memory World.")
        world = World()  # Create a fresh world
        onto = world.get_ontology(ontology_iri)
        logger.info(f"Ontology object created in memory: {onto}")
    return world, onto

def _define_tbox(onto, specification, strict_adherence, skip_classes, logger):
    logger.info("Defining ontology structure (TBox)...")
    if strict_adherence or skip_classes:
        logger.info("Using selective class creation based on config.")
        defined_classes = create_selective_classes(onto, specification,
                                                  skip_classes=skip_classes,
                                                  strict_adherence=strict_adherence)
        # Define properties separately when using selective classes
        _, defined_properties, property_is_functional = define_ontology_structure(onto, specification)
    else:
        defined_classes, defined_properties, property_is_functional = define_ontology_structure(onto, specification)

    if not defined_classes:
        logger.warning("Ontology structure definition resulted in no classes. Population might be empty.")
    logger.info("TBox definition complete.")
    return defined_classes, defined_properties, property_is_functional

def _read_operational_data(data_file_path, logger):
    logger.info(f"Reading operational data from: {data_file_path}")
    try:
        data_rows = read_data(data_file_path)
        logger.info(f"Read {len(data_rows)} data rows.")
        if not data_rows:
            logger.warning("No data rows read. Ontology population will be skipped.")
        return data_rows
    except Exception as read_err:
        logger.error(f"Failed to read data file {data_file_path}: {read_err}", exc_info=True)
        return None # Indicate failure

def _populate_abox(onto, data_rows, defined_classes, defined_properties, prop_is_functional, specification, property_mappings, logger):
    logger.info("Starting ontology population (ABox)...")
    population_successful = True
    failed_rows_count = 0
    created_eq_classes = {}
    eq_class_positions = {}
    created_events_context = []
    all_created_individuals_by_uid = {}

    if not data_rows:
        logger.warning("Skipping population as no data rows were provided.")
        # Return success=True but with zero counts/empty contexts
        return True, 0, {}, {}, [], {}

    try:
        failed_rows_count, created_eq_classes, eq_class_positions, created_events_context, all_created_individuals_by_uid = populate_ontology_from_data(
            onto, data_rows, defined_classes, defined_properties, prop_is_functional,
            specification, property_mappings
        )
        if failed_rows_count == len(data_rows) and len(data_rows) > 0:
            logger.error(f"Population failed for all {len(data_rows)} data rows.")
            population_successful = False
        elif failed_rows_count > 0:
            logger.warning(f"Population completed with {failed_rows_count} out of {len(data_rows)} failed rows.")
        else:
            logger.info(f"Population completed successfully for all {len(data_rows)} rows.")

    except Exception as pop_exc:
        logger.error(f"Critical error during population: {pop_exc}", exc_info=True)
        population_successful = False

    logger.info("ABox population phase finished.")
    return population_successful, failed_rows_count, created_eq_classes, eq_class_positions, created_events_context, all_created_individuals_by_uid

def _run_analysis_and_optimization(onto, defined_classes, specification, optimize_ontology, output_owl_path, logger):
    logger.info("Analyzing ontology population status...")
    try:
        population_counts, empty_classes, class_instances, class_usage_info = analyze_ontology_population(onto, defined_classes, specification)
        population_report = generate_population_report(population_counts, empty_classes, class_instances, defined_classes, class_usage_info)
        logger.info("Ontology Population Analysis Complete")
        print(population_report) # Print to console

        if optimize_ontology:
            logger.info("Generating detailed optimization recommendations...")
            optimization_recs = generate_optimization_recommendations(class_usage_info, defined_classes)
            print("\n=== DETAILED OPTIMIZATION RECOMMENDATIONS ===")
            if optimization_recs.get('classes_to_remove'):
                print(f"\nClasses that could be safely removed ({len(optimization_recs['classes_to_remove'])}):")
                for class_name in optimization_recs['classes_to_remove']:
                    print(f"  • {class_name}")
            if optimization_recs.get('configuration_options'):
                print("\nSuggested configuration for future runs:")
                for option in optimization_recs['configuration_options']:
                    print(f"  • {option}")
            # Save recommendations to file
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
                logger.info(f"Saved optimization recommendations to {recs_file}")
            except Exception as e:
                logger.error(f"Failed to save optimization recommendations: {e}")

    except Exception as analysis_exc:
        logger.error(f"Error analyzing ontology population: {analysis_exc}", exc_info=False)
        # Continue despite analysis failure

def _setup_sequence_relationships(onto, created_eq_classes, eq_class_positions, defined_classes, defined_properties, property_is_functional, logger):
    logger.info("Setting up equipment instance relationships...")
    try:
        # Only set up instance-level relationships
        setup_equipment_instance_relationships(onto, defined_classes, defined_properties, property_is_functional, eq_class_positions)
        logger.info("Equipment instance sequence relationship setup complete.")
        
        # Add equipment sequence report generation
        sequence_report = generate_equipment_sequence_report(onto)
        logger.info("Equipment sequence report generated.")
        print(sequence_report)  # Print to console for immediate visibility
        
    except Exception as seq_exc:
        logger.error(f"Error during sequence relationship setup: {seq_exc}", exc_info=True)
        # Log error but continue

def _link_equipment_events(onto, created_events_context, defined_classes, defined_properties, logger, event_buffer_minutes=None):
    logger.info("Linking equipment events to line events...")
    try:
        links_made = link_equipment_events_to_line_events(
            onto, created_events_context, defined_classes, defined_properties, event_buffer_minutes
        )
        logger.info(f"Event linking pass created {links_made} links.")
    except Exception as link_exc:
        logger.error(f"Error during event linking pass: {link_exc}", exc_info=True)
        # Log error but continue

def _process_structural_relationships(onto, data_rows, defined_classes, defined_properties, property_is_functional, property_mappings, all_created_individuals_by_uid, logger):
    """
    Process structural relationships between entities after all individuals have been created.
    This is specifically for relationships that can't be established during row-by-row processing.
    
    Args:
        onto: The ontology being populated
        data_rows: The data rows (used for referencing column information)
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties 
        property_is_functional: Dictionary indicating whether properties are functional
        property_mappings: Parsed property mappings
        all_created_individuals_by_uid: Registry of all created individuals
        logger: Logger to use
    
    Returns:
        int: Number of structural links created
    """
    logger.info("Processing structural relationships between entities...")
    try:
        # Import the function from row_processor
        from ontology_generator.population.row_processor import process_structural_relationships
        from ontology_generator.population.core import PopulationContext
        
        # Create the context
        context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)
        
        # Call the structural relationship processor
        links_created = process_structural_relationships(
            context, property_mappings, all_created_individuals_by_uid, logger
        )
        
        logger.info(f"Structural relationship processing complete. Created {links_created} links.")
        return links_created
    except Exception as e:
        logger.error(f"Error processing structural relationships: {e}", exc_info=True)
        return 0  # Indicate no links were created due to error

def _run_reasoning_phase(onto, world, world_db_path, reasoner_report_max_entities, reasoner_report_verbose, logger):
    logger.info("Applying reasoner (ensure HermiT or compatible reasoner is installed)...")
    reasoning_successful = True
    try:
        active_world = world if world_db_path else default_world
        with onto:
            pre_stats = {
                'classes': len(list(onto.classes())), 'object_properties': len(list(onto.object_properties())),
                'data_properties': len(list(onto.data_properties())), 'individuals': len(list(onto.individuals()))
            }
            logger.info("Starting reasoning process...")
            reasoning_start_time = timing.time()
            sync_reasoner(infer_property_values=True, debug=0) # Pass world implicitly via onto context?
            reasoning_end_time = timing.time()
            logger.info(f"Reasoning finished in {reasoning_end_time - reasoning_start_time:.2f} seconds.")

            # Post-reasoning analysis and report generation
            inconsistent = list(active_world.inconsistent_classes())
            inferred_hierarchy = {}
            inferred_properties = {}
            inferred_individuals = {}
            for cls in onto.classes():
                current_subclasses = set(cls.subclasses())
                inferred_subs = [sub.name for sub in current_subclasses if sub != cls and sub != Nothing] 
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
                inferred_chars_for_prop = [char_name for char_name, char_class in inferrable_chars.items() if char_class in prop.is_a]
                if inferred_chars_for_prop: inferred_properties[prop.name] = inferred_chars_for_prop

            logger.info("Collecting simplified individual inferences (post-reasoning state).")
            for ind in onto.individuals():
                current_types = [c.name for c in ind.is_a if c is not Thing]
                current_props = {}
                for prop in list(onto.object_properties()) + list(onto.data_properties()):
                    try:
                        values = prop[ind]
                        if not isinstance(values, list): values = [values] if values is not None else []
                        if values:
                            formatted_values = []
                            for v in values:
                                if isinstance(v, Thing): formatted_values.append(v.name)
                                elif isinstance(v, locstr): formatted_values.append(f'"{v}"@{v.lang}')
                                else: formatted_values.append(repr(v))
                            if formatted_values: current_props[prop.name] = formatted_values
                    except Exception: continue
                if current_types or current_props:
                    inferred_individuals[ind.name] = {'types': current_types, 'properties': current_props}

            post_stats = {
                'classes': len(list(onto.classes())), 'object_properties': len(list(onto.object_properties())),
                'data_properties': len(list(onto.data_properties())), 'individuals': len(list(onto.individuals()))
            }
            report, has_issues = generate_reasoning_report(
                onto, pre_stats, post_stats, inconsistent, inferred_hierarchy,
                inferred_properties, inferred_individuals, True, # Assuming reasoner ran
                max_entities_per_category=reasoner_report_max_entities,
                verbose=reasoner_report_verbose
            )
            logger.info("\nReasoning Report:\n" + report)

            if has_issues or inconsistent:
                logger.warning("Reasoning completed but potential issues or inconsistencies were identified.")
                if inconsistent: reasoning_successful = False
            else: logger.info("Reasoning completed successfully.")

    except OwlReadyInconsistentOntologyError:
        logger.error("REASONING FAILED: Ontology is inconsistent!")
        reasoning_successful = False
        try:
            active_world = world if world_db_path else default_world
            inconsistent = list(active_world.inconsistent_classes())
            logger.error(f"Inconsistent classes detected: {[c.name for c in inconsistent]}")
        except Exception as e_inc: logger.error(f"Could not retrieve inconsistent classes: {e_inc}")
    except NameError as ne:
        if "sync_reasoner" in str(ne): logger.error("Reasoning failed: Reasoner (sync_reasoner) function not found.")
        else: logger.error(f"Unexpected NameError during reasoning: {ne}")
        reasoning_successful = False
    except Exception as e:
        logger.error(f"An error occurred during reasoning: {e}", exc_info=True)
        reasoning_successful = False

    logger.info("Reasoning phase finished.")
    return reasoning_successful

def _save_ontology_file(onto, world, output_owl_path, save_format, world_db_path, population_successful, reasoning_successful, logger):
    should_save_primary = population_successful and reasoning_successful
    final_output_path = output_owl_path
    save_failed = False

    if not should_save_primary:
        logger.error("Ontology generation had issues (population/reasoning failure/inconsistency). Saving to debug file instead.")
        base, ext = os.path.splitext(output_owl_path)
        debug_output_path = f"{base}_debug{ext}"
        if debug_output_path == output_owl_path:
            debug_output_path = output_owl_path + "_debug"
        final_output_path = debug_output_path
        logger.info(f"Attempting to save potentially problematic ontology to: {final_output_path}")
    else:
        logger.info(f"Attempting to save final ontology to: {final_output_path}")

    logger.info(f"Saving ontology in '{save_format}' format...")
    try:
        # Use the world associated with the ontology for saving, especially if persistent
        # If world is None (in-memory case after setup failure?), this will likely fail, which is ok.
        onto.save(file=final_output_path, format=save_format)
        logger.info("Ontology saved successfully.")
    except Exception as save_err:
        logger.error(f"Failed to save ontology to {final_output_path}: {save_err}", exc_info=True)
        save_failed = True # Indicate saving failed

    return save_failed

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
                             optimize_ontology: bool = False,
                             event_buffer_minutes: Optional[int] = None
                            ) -> bool:
    """
    Main function to generate the ontology by orchestrating helper functions.
    (Args documentation remains the same)
    Returns:
        bool: True on overall success, False on failure
    """
    start_time = timing.time()
    main_logger.info("--- Ontology Generation Process Started ---")

    # Use a dummy args object for logging if needed, or adapt helpers
    # For simplicity, let's create a temporary Namespace-like object
    class Args: pass
    args = Args()
    args.spec_file = spec_file_path
    args.data_file = data_file_path
    args.output_file = output_owl_path
    args.iri = ontology_iri
    args.format = save_format
    args.reasoner = use_reasoner
    args.worlddb = world_db_path
    args.max_report_entities = reasoner_report_max_entities
    args.full_report = reasoner_report_verbose
    args.analyze_population = analyze_population
    args.strict_adherence = strict_adherence
    args.skip_classes = skip_classes
    args.optimize_ontology = optimize_ontology
    args.event_buffer_minutes = event_buffer_minutes

    world = None
    onto = None
    population_successful = False
    reasoning_successful = True # Assume success unless reasoner runs and fails
    save_failed = False

    try:
        # 1. Log Initial Parameters
        _log_initial_parameters(args, main_logger)

        # 2. Parse Specification and Mappings
        specification, property_mappings = _parse_spec_and_mappings(args.spec_file, main_logger)
        if specification is None: return False

        # 3. Setup World and Ontology
        world, onto = _setup_world_and_ontology(args.iri, args.worlddb, main_logger)
        if onto is None: return False

        # 4. Define Ontology Structure (TBox)
        defined_classes, defined_properties, property_is_functional = _define_tbox(
            onto, specification, args.strict_adherence, args.skip_classes, main_logger
        )
        # Handle case where TBox definition might yield nothing critical?
        # Current _define_tbox logs warning, main flow continues.

        # 5. Read Operational Data
        data_rows = _read_operational_data(args.data_file, main_logger)
        if data_rows is None: return False # Indicate failure if reading failed

        # 6. Populate Ontology (ABox)
        population_successful, failed_rows_count, created_eq_classes, eq_class_positions, created_events_context, all_created_individuals_by_uid = _populate_abox(
            onto, data_rows, defined_classes, defined_properties, property_is_functional,
            specification, property_mappings, main_logger
        )
        
        # 7. Process Structural Relationships (NEW STEP)
        if population_successful:
            # Process structural relationships with the registry from population
            _process_structural_relationships(
                onto, data_rows, defined_classes, defined_properties, property_is_functional,
                property_mappings, all_created_individuals_by_uid, main_logger
            )
            main_logger.info("Structural relationship processing complete.")

        # 8. Analyze Population & Optimize (Optional)
        if population_successful and args.analyze_population:
            _run_analysis_and_optimization(onto, defined_classes, specification, args.optimize_ontology, args.output_file, main_logger)
        elif not args.analyze_population:
            main_logger.warning("Skipping ontology population analysis as requested.")

        # 9. Setup Sequence Relationships (Optional)
        if population_successful and created_eq_classes:
             _setup_sequence_relationships(onto, created_eq_classes, eq_class_positions, defined_classes, defined_properties, property_is_functional, main_logger)
        elif population_successful:
             main_logger.warning("Skipping sequence relationship setup: No EquipmentClass individuals found during population.")
        # No action needed if population failed, handled by checks below

        # 10. Link Events (Optional)
        if created_events_context:
            _link_equipment_events(
                onto, created_events_context, defined_classes, defined_properties, 
                main_logger, args.event_buffer_minutes
            )
        else:
            main_logger.warning("No event context data available for linking. Event linking skipped.")

        # 11. Apply Reasoning (Optional)
        if args.reasoner and population_successful:
            reasoning_successful = _run_reasoning_phase(onto, world, args.worlddb, args.max_report_entities, args.full_report, main_logger)
        elif args.reasoner and not population_successful:
            main_logger.warning("Skipping reasoning due to prior population failure.")
            reasoning_successful = False # Ensure overall success reflects this skipped step
        # If reasoner not used, reasoning_successful remains True

        # 12. Save Ontology
        # Saving logic depends on population and reasoning success
        # The helper returns True if saving *failed*
        save_failed = _save_ontology_file(onto, world, args.output_file, args.format, args.worlddb, population_successful, reasoning_successful, main_logger)
        if save_failed:
            return False # Saving failed, overall process is unsuccessful

        # 13. Determine overall success
        overall_success = population_successful and reasoning_successful and not save_failed
        return overall_success

    except Exception as e:
        main_logger.exception("A critical error occurred during the overall ontology generation process.")
        return False

    finally:
        end_time = timing.time()
        main_logger.info(f"--- Ontology Generation Finished --- Total time: {end_time - start_time:.2f} seconds")
        
        # Log suppressed message counts
        from ontology_generator.utils.logging import log_suppressed_message_counts
        log_suppressed_message_counts()


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


def analyze_equipment_sequence_in_ontology(owl_file_path: str, verbose: bool = False) -> bool:
    """
    Standalone function to analyze equipment sequences in an existing ontology file.
    
    Args:
        owl_file_path: Path to the OWL file to analyze
        verbose: Enable verbose output
        
    Returns:
        True if analysis was successful, False otherwise
    """
    # Configure logging
    configure_logging(logging.DEBUG if verbose else logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Import here to avoid circular imports
        from ontology_generator.analysis.sequence_analysis import (
            generate_equipment_sequence_report, 
            analyze_equipment_sequences,
            generate_enhanced_sequence_report
        )
        from owlready2 import get_ontology, IRIS
        
        logger.info(f"Loading ontology from {owl_file_path} for sequence analysis...")
        # Initialize owlready2 world and load ontology
        from owlready2 import World
        world = World()
        onto = world.get_ontology(owl_file_path).load()
        
        # Get namespace
        IRIS.prefixes[""] = onto.base_iri
        
        logger.info(f"Loaded ontology: {onto.base_iri}")
        
        # Generate and print the standard equipment sequence report
        sequence_report = generate_equipment_sequence_report(onto)
        print(sequence_report)
        
        # Generate and print the enhanced sequence report 
        enhanced_report = generate_enhanced_sequence_report(onto)
        print(enhanced_report)
        
        # Run deeper analysis if verbose
        if verbose:
            sequences, stats = analyze_equipment_sequences(onto)
            print("\n=== EQUIPMENT SEQUENCE STATISTICS ===")
            print(f"Total Lines: {stats['total_lines']}")
            print(f"Lines with Equipment Sequence: {stats['lines_with_sequence']}")
            print(f"Total Equipment in Sequences: {stats['total_equipment']}")
            print("\nEquipment Classes:")
            for cls, count in sorted(stats.get('class_counts', {}).items(), key=lambda x: x[1], reverse=True):
                print(f"  {cls}: {count}")
        
        return True
    except Exception as e:
        logger.error(f"Error analyzing equipment sequences: {e}", exc_info=True)
        return False

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
    parser.add_argument("--analyze-sequences", metavar="OWL_FILE", help="Analyze equipment sequences in an existing ontology file.")
    parser.add_argument("--event-buffer", type=int, default=None, metavar="MINUTES", 
                       help=f"Time buffer in minutes for event linking (default: {DEFAULT_EVENT_LINKING_BUFFER_MINUTES}).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO level logging.")

    args = parser.parse_args()

    # If analyze-sequences mode is requested, just run the analysis and exit
    if hasattr(args, 'analyze_sequences') and args.analyze_sequences:
        success = analyze_equipment_sequence_in_ontology(args.analyze_sequences, args.verbose)
        sys.exit(0 if success else 1)

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
        optimize_ontology=args.optimize_ontology,
        event_buffer_minutes=args.event_buffer
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
