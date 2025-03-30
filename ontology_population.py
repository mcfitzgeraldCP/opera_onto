# ontology_population.py
# -*- coding: utf-8 -*-
"""
Populates the OWL ontology (ABox) with individuals and relationships
based on input data conforming to the sample structure.
"""
import csv
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from owlready2 import *

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def parse_equipment_class(equipment_name):
    """
    Parses the EquipmentClass from the EQUIPMENT_NAME.
    Rule: EQUIPMENT_NAME:FIPCO009_Filler becomes EquipmentClass:Filler
    If no underscore, use the whole name? Assume part after last underscore.
    """
    if not equipment_name or not isinstance(equipment_name, str):
        return None
    if '_' in equipment_name:
        return equipment_name.split('_')[-1]
    return equipment_name # Fallback if no underscore

def safe_cast(value, target_type, default=None):
    """Safely casts a value to a target type, returning default on failure."""
    if value is None or value == '':
        return default
    try:
        if target_type is str:
            return str(value).strip()
        if target_type is int:
            # Handle potential floats in data like '224.0' for EQUIPMENT_ID
            return int(float(value))
        if target_type is float:
            return float(value)
        if target_type is Decimal:
             # Remove commas if present, e.g., in rates
             cleaned_value = str(value).replace(',', '')
             return Decimal(cleaned_value)
        if target_type is bool:
            # Handle various boolean string representations
            val_lower = str(value).strip().lower()
            if val_lower in ['true', '1', 't', 'y', 'yes']:
                return True
            elif val_lower in ['false', '0', 'f', 'n', 'no']:
                return False
            else:
                logger.warning(f"Could not interpret '{value}' as boolean.")
                return default
        if target_type is datetime:
            # Try parsing common formats, including the one in the sample data
            # '2025-02-05 22:40:21.000 -0500'
            # owlready2 stores datetime naive, stripping timezone info after parsing
            fmts = [
                "%Y-%m-%d %H:%M:%S.%f %z", # Format with timezone
                "%Y-%m-%d %H:%M:%S %z",
                "%Y-%m-%d %H:%M:%S.%f",    # Format without timezone
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]
            parsed_dt = None
            for fmt in fmts:
                try:
                    # Remove trailing Z if present before parsing timezone
                    clean_value = str(value).strip()
                    if clean_value.endswith('Z'):
                       clean_value = clean_value[:-1] + '+0000'

                    parsed_dt = datetime.strptime(clean_value, fmt)
                    # Make timezone-aware if timezone info was present, then convert to UTC?
                    # owlready2 seems to prefer naive datetimes, let's keep them naive for now
                    # if parsed_dt.tzinfo:
                    #     parsed_dt = parsed_dt.astimezone(timezone.utc).replace(tzinfo=None)

                    logger.debug(f"Successfully parsed datetime '{value}' using format '{fmt}' -> {parsed_dt}")
                    return parsed_dt
                except ValueError:
                    continue # Try next format
            if parsed_dt is None:
                 logger.warning(f"Could not parse datetime string '{value}' with known formats.")
                 return default

        # Add other types like date, time if needed
        return target_type(value) # General cast attempt
    except (ValueError, TypeError, InvalidOperation) as e:
        logger.warning(f"Failed to cast '{value}' to {target_type.__name__}: {e}. Returning default: {default}")
        return default

def get_or_create_individual(onto_class, individual_name, onto, extra_label=None):
    """Gets an individual if it exists, otherwise creates it."""
    if not individual_name:
        logger.warning(f"Cannot get/create individual with empty name for class {onto_class.name}")
        return None

    # Sanitize name for IRI (replace spaces, etc.) - Basic example
    # A more robust IRI sanitization might be needed depending on data
    safe_name = re.sub(r'\s+', '_', str(individual_name).strip())
    safe_name = re.sub(r'[^\w\-.]', '', safe_name) # Keep word chars, hyphen, period
    if not safe_name: # Handle cases where name becomes empty after sanitization
         safe_name = f"{onto_class.name}_unnamed_{hash(individual_name)}" # Generate a fallback

    individual = onto[safe_name]
    if individual and isinstance(individual, onto_class):
        logger.debug(f"Retrieved existing individual: {individual.iri}")
        return individual
    elif individual: # Exists but wrong type? Log warning. Should not happen often with unique names.
         logger.warning(f"Individual {safe_name} exists but is not of type {onto_class.name}. Type is {type(individual)}. Reusing might be problematic.")
         return individual # Return existing one anyway? Or create new? Let's try creating a new one with suffix.
         # safe_name = f"{safe_name}_type_{onto_class.name}" # Try alternative name
         # individual = onto[safe_name] # Check again
         # if individual: return individual # If alternative exists, use it

    try:
        logger.debug(f"Creating new individual '{safe_name}' of class {onto_class.name}")
        new_individual = onto_class(safe_name)
        if extra_label and individual_name != extra_label: # Add original name as label if sanitized
             new_individual.label.append(str(individual_name))
        if extra_label:
             new_individual.label.append(str(extra_label))
        return new_individual
    except Exception as e:
        logger.error(f"Failed to create individual '{safe_name}' of class {onto_class.name}: {e}")
        return None


# --- Main Population Function ---

def populate_ontology_from_data(onto, data_rows, defined_classes, defined_properties):
    """
    Populates the ontology with individuals and relations from data rows.

    Args:
        onto: The owlready2 ontology object.
        data_rows: A list of dictionaries, where each dictionary represents a row
                   from the input data CSV.
        defined_classes: Dictionary mapping class names to owlready2 class objects.
        defined_properties: Dictionary mapping property names to owlready2 property objects.
    """
    logger.info(f"Starting ontology population with {len(data_rows)} data rows.")

    # Get class and property objects using their names (assuming they are defined)
    # We fetch them here to avoid repeated lookups in the loop
    cls_Plant = defined_classes.get("Plant")
    cls_Area = defined_classes.get("Area")
    cls_ProcessCell = defined_classes.get("ProcessCell")
    cls_ProductionLine = defined_classes.get("ProductionLine")
    cls_Equipment = defined_classes.get("Equipment")
    cls_EquipmentClass = defined_classes.get("EquipmentClass")
    cls_Material = defined_classes.get("Material")
    cls_ProductionRequest = defined_classes.get("ProductionRequest")
    cls_EventRecord = defined_classes.get("EventRecord")
    cls_TimeInterval = defined_classes.get("TimeInterval")
    cls_Shift = defined_classes.get("Shift")
    cls_OperationalState = defined_classes.get("OperationalState")
    cls_OperationalReason = defined_classes.get("OperationalReason")
    # Add Personnel, Capability, Sequence etc. classes if needed based on data

    prop_plantId = defined_properties.get("plantId")
    prop_areaId = defined_properties.get("areaId")
    prop_processCellId = defined_properties.get("processCellId")
    prop_lineId = defined_properties.get("lineId")
    prop_equipmentId = defined_properties.get("equipmentId")
    prop_equipmentName = defined_properties.get("equipmentName")
    prop_equipmentClassId = defined_properties.get("equipmentClassId")
    prop_equipmentModel = defined_properties.get("equipmentModel")
    prop_complexity = defined_properties.get("complexity")
    prop_alternativeModel = defined_properties.get("alternativeModel")
    prop_memberOfClass = defined_properties.get("memberOfClass")
    prop_materialId = defined_properties.get("materialId")
    prop_materialDescription = defined_properties.get("materialDescription")
    prop_sizeType = defined_properties.get("sizeType")
    prop_materialUOM = defined_properties.get("materialUOM")
    prop_standardUOM = defined_properties.get("standardUOM")
    prop_targetProductUOM = defined_properties.get("targetProductUOM")
    prop_conversionFactor = defined_properties.get("conversionFactor")
    prop_requestId = defined_properties.get("requestId")
    prop_requestDescription = defined_properties.get("requestDescription")
    prop_requestRate = defined_properties.get("requestRate")
    prop_requestRateUOM = defined_properties.get("requestRateUOM")
    prop_startTime = defined_properties.get("startTime")
    prop_endTime = defined_properties.get("endTime")
    prop_shiftId = defined_properties.get("shiftId")
    prop_shiftStartTime = defined_properties.get("shiftStartTime")
    prop_shiftEndTime = defined_properties.get("shiftEndTime")
    prop_shiftDurationMinutes = defined_properties.get("shiftDurationMinutes")
    prop_rampUpFlag = defined_properties.get("rampUpFlag")
    prop_operationType = defined_properties.get("operationType")
    prop_reportedDurationMinutes = defined_properties.get("reportedDurationMinutes")
    prop_businessExternalTimeMinutes = defined_properties.get("businessExternalTimeMinutes")
    prop_plantAvailableTimeMinutes = defined_properties.get("plantAvailableTimeMinutes")
    prop_effectiveRuntimeMinutes = defined_properties.get("effectiveRuntimeMinutes")
    prop_plantDecisionTimeMinutes = defined_properties.get("plantDecisionTimeMinutes")
    prop_productionAvailableTimeMinutes = defined_properties.get("productionAvailableTimeMinutes")

    # Object Properties for linking (assuming names from spec - may need helper function if names differ)
    prop_locatedInPlant = defined_properties.get("locatedInPlant") # Assumed inverse of plantHasArea or similar - Spec doesn't define clearly
    prop_partOfArea = defined_properties.get("partOfArea") # Assumed inverse of areaHasProcessCell
    prop_locatedInProcessCell = defined_properties.get("locatedInProcessCell") # Assumed inverse
    prop_isPartOfProductionLine = defined_properties.get("isPartOfProductionLine") # Assumed inverse
    prop_involvesResource = defined_properties.get("involvesResource")
    prop_associatedWithProductionRequest = defined_properties.get("associatedWithProductionRequest") # Assumed - links EventRecord to ProdReq
    prop_usesMaterial = defined_properties.get("usesMaterial") # Assumed - links EventRecord/ProdReq to Material
    prop_occursDuring = defined_properties.get("occursDuring") # Assumed - links EventRecord to TimeInterval
    prop_duringShift = defined_properties.get("duringShift") # Links EventRecord to Shift

    # Need to add properties for OperationalState/Reason if linking them as objects
    prop_eventHasState = defined_properties.get("eventHasState") # Assumed - links EventRecord to State
    prop_eventHasReason = defined_properties.get("eventHasReason") # Assumed - links EventRecord to Reason
    prop_stateDescription = defined_properties.get("stateDescription")
    prop_reasonDescription = defined_properties.get("reasonDescription")
    prop_altReasonDescription = defined_properties.get("altReasonDescription")
    prop_downtimeDriver = defined_properties.get("downtimeDriver")
    prop_changeoverType = defined_properties.get("changeoverType")


    # --- Check if essential classes/properties exist ---
    essential_classes = [cls_Plant, cls_Area, cls_ProcessCell, cls_ProductionLine, cls_Equipment, cls_EquipmentClass, cls_Material, cls_ProductionRequest, cls_EventRecord, cls_TimeInterval, cls_Shift, cls_OperationalState, cls_OperationalReason]
    if not all(essential_classes):
         missing = [name for name, cls in zip(["Plant", "Area", "ProcessCell", "ProductionLine", "Equipment", "EquipmentClass", "Material", "ProductionRequest", "EventRecord", "TimeInterval", "Shift", "OperationalState", "OperationalReason"], essential_classes) if not cls]
         logger.error(f"Cannot proceed with population. Missing essential classes: {missing}")
         return

    # Add checks for essential properties if needed

    with onto: # Use the ontology context for creating individuals
        processed_ids = set() # To avoid redundant processing if data has duplicates?

        for i, row in enumerate(data_rows):
            try:
                # --- Create / Retrieve Core Asset Hierarchy Individuals ---
                plant_id = safe_cast(row.get('PLANT'), str)
                plant_ind = get_or_create_individual(cls_Plant, plant_id, onto)
                if plant_ind and prop_plantId: plant_ind.plantId = [plant_id] # Use list assignment even for functional for consistency

                area_id = safe_cast(row.get('GH_FOCUSFACTORY'), str) # Using FocusFactory as Area ID based on spec
                area_ind = get_or_create_individual(cls_Area, f"{plant_id}_{area_id}", onto, extra_label=area_id)
                if area_ind:
                    if prop_areaId: area_ind.areaId = [area_id]
                    # Add relationship: Area locatedInPlant Plant (Need 'locatedInPlant' property)
                    # Assuming 'locatedInPlant' exists - add check later
                    # if prop_locatedInPlant and plant_ind: area_ind.locatedInPlant = [plant_ind]

                pcell_id = safe_cast(row.get('PHYSICAL_AREA'), str) # Using PhysicalArea as ProcessCell ID
                pcell_ind = get_or_create_individual(cls_ProcessCell, f"{plant_id}_{area_id}_{pcell_id}", onto, extra_label=pcell_id)
                if pcell_ind:
                    if prop_processCellId: pcell_ind.processCellId = [pcell_id]
                    # Add relationship: ProcessCell partOfArea Area (Need 'partOfArea' property)
                    # if prop_partOfArea and area_ind: pcell_ind.partOfArea = [area_ind]


                line_id = safe_cast(row.get('LINE_NAME'), str)
                line_ind = get_or_create_individual(cls_ProductionLine, f"{plant_id}_{area_id}_{pcell_id}_{line_id}", onto, extra_label=line_id)
                if line_ind:
                     if prop_lineId: line_ind.lineId = [line_id]
                     # Add relationship: ProductionLine locatedInProcessCell ProcessCell (Need 'locatedInProcessCell' property)
                     # if prop_locatedInProcessCell and pcell_ind: line_ind.locatedInProcessCell = [pcell_ind]


                eq_id_raw = row.get('EQUIPMENT_ID')
                eq_id_str = safe_cast(eq_id_raw, str) # Keep as string for URI/name
                eq_name = safe_cast(row.get('EQUIPMENT_NAME'), str)
                eq_type = safe_cast(row.get('EQUIPMENT_TYPE'), str) # 'Line' or 'Equipment'

                equipment_ind = None
                resource_individual = None # This will hold the individual linked by EventRecord

                if eq_type == 'Line':
                     # If the record is for a Line, use the line individual already created
                     resource_individual = line_ind
                     logger.debug(f"Row {i}: Identified as Line record for: {line_id}")

                elif eq_type == 'Equipment' and eq_id_str:
                    # Create Equipment individual
                    equipment_ind = get_or_create_individual(cls_Equipment, f"Eq_{eq_id_str}", onto, extra_label=eq_name)
                    if equipment_ind:
                         if prop_equipmentId: equipment_ind.equipmentId = [eq_id_str] # Use the original parsed ID here
                         if prop_equipmentName: equipment_ind.equipmentName = [eq_name]
                         if prop_equipmentModel: equipment_ind.equipmentModel = [safe_cast(row.get('EQUIPMENT_MODEL'), str)]
                         if prop_complexity: equipment_ind.complexity = [safe_cast(row.get('COMPLEXITY'), str)]
                         if prop_alternativeModel: equipment_ind.alternativeModel = [safe_cast(row.get('MODEL'), str)]

                         # Link Equipment to ProductionLine (Need 'isPartOfProductionLine' property)
                         # if prop_isPartOfProductionLine and line_ind: equipment_ind.isPartOfProductionLine = [line_ind]

                         # Parse and link EquipmentClass
                         eq_class_name = parse_equipment_class(eq_name)
                         if eq_class_name:
                             eq_class_ind = get_or_create_individual(cls_EquipmentClass, eq_class_name, onto)
                             if eq_class_ind:
                                 if prop_equipmentClassId: eq_class_ind.equipmentClassId = [eq_class_name]
                                 if prop_memberOfClass: equipment_ind.memberOfClass = [eq_class_ind]
                         else:
                              logger.warning(f"Row {i}: Could not parse EquipmentClass from EQUIPMENT_NAME: {eq_name}")

                         resource_individual = equipment_ind # The event involves this equipment
                         logger.debug(f"Row {i}: Identified as Equipment record for: {eq_id_str}")

                else:
                    logger.warning(f"Row {i}: Could not determine resource type or missing ID. EQUIPMENT_TYPE='{eq_type}', EQUIPMENT_ID='{eq_id_raw}'")
                    continue # Skip if we can't identify the main resource


                # --- Create Material Individual ---
                mat_id = safe_cast(row.get('MATERIAL_ID'), str)
                mat_ind = None
                if mat_id:
                    mat_ind = get_or_create_individual(cls_Material, f"Mat_{mat_id}", onto, extra_label=row.get('SHORT_MATERIAL_ID'))
                    if mat_ind:
                         if prop_materialId: mat_ind.materialId = [mat_id]
                         if prop_materialDescription: mat_ind.materialDescription = [safe_cast(row.get('SHORT_MATERIAL_ID'), str)]
                         if prop_sizeType: mat_ind.sizeType = [safe_cast(row.get('SIZE_TYPE'), str)]
                         if prop_materialUOM: mat_ind.materialUOM = [safe_cast(row.get('MATERIAL_UOM'), str)]
                         # Handle combined UOM columns if necessary
                         uom_st = safe_cast(row.get('UOM_ST'), str) or safe_cast(row.get('UOM_ST_SAP'), str)
                         if prop_standardUOM and uom_st: mat_ind.standardUOM = [uom_st]
                         if prop_targetProductUOM: mat_ind.targetProductUOM = [safe_cast(row.get('TP_UOM'), str)]
                         if prop_conversionFactor: mat_ind.conversionFactor = [safe_cast(row.get('PRIMARY_CONV_FACTOR'), Decimal)]


                # --- Create Production Request Individual ---
                req_id = safe_cast(row.get('PRODUCTION_ORDER_ID'), str)
                req_ind = None
                if req_id:
                    req_ind = get_or_create_individual(cls_ProductionRequest, f"Req_{req_id}", onto, extra_label=row.get('PRODUCTION_ORDER_DESC'))
                    if req_ind:
                        if prop_requestId: req_ind.requestId = [req_id]
                        if prop_requestDescription: req_ind.requestDescription = [safe_cast(row.get('PRODUCTION_ORDER_DESC'), str)]
                        if prop_requestRate: req_ind.requestRate = [safe_cast(row.get('PRODUCTION_ORDER_RATE'), Decimal)]
                        if prop_requestRateUOM: req_ind.requestRateUOM = [safe_cast(row.get('PRODUCTION_ORDER_UOM'), str)]
                        # Link ProductionRequest to Material if needed (requires property)
                        # if prop_usesMaterial and mat_ind: req_ind.usesMaterial = [mat_ind]


                # --- Create Shift Individual ---
                shift_name = safe_cast(row.get('SHIFT_NAME'), str)
                shift_ind = None
                if shift_name:
                     # Make shift name unique per day to handle overlaps if needed? Or assume name is unique enough?
                     # For simplicity, assume shift name is the ID for now.
                     shift_ind = get_or_create_individual(cls_Shift, shift_name, onto)
                     if shift_ind:
                          if prop_shiftId: shift_ind.shiftId = [shift_name]
                          # Populate shift times only once per shift instance? Check if already set.
                          # Using list assignment overwrites, so it works okay even if called multiple times.
                          if prop_shiftStartTime: shift_ind.shiftStartTime = [safe_cast(row.get('SHIFT_START_DATE_LOC'), datetime)]
                          if prop_shiftEndTime: shift_ind.shiftEndTime = [safe_cast(row.get('SHIFT_END_DATE_LOC'), datetime)]
                          if prop_shiftDurationMinutes: shift_ind.shiftDurationMinutes = [safe_cast(row.get('SHIFT_DURATION_MIN'), Decimal)]


                # --- Create Operational State and Reason Individuals ---
                # Link EventRecord to these via properties like eventHasState/eventHasReason
                state_desc = safe_cast(row.get('UTIL_STATE_DESCRIPTION'), str)
                state_ind = None
                if state_desc and cls_OperationalState:
                    # Create unique state instance based on description?
                    state_name = f"State_{re.sub(r'[^a-zA-Z0-9]', '', state_desc)}" # Basic sanitization
                    state_ind = get_or_create_individual(cls_OperationalState, state_name, onto, extra_label=state_desc)
                    if state_ind and prop_stateDescription:
                        # Ensure description is set (might be first time seeing this state)
                        if not state_ind.stateDescription:
                            state_ind.stateDescription = [state_desc]

                reason_desc = safe_cast(row.get('UTIL_REASON_DESCRIPTION'), str)
                reason_ind = None
                if reason_desc and cls_OperationalReason:
                    reason_name = f"Reason_{re.sub(r'[^a-zA-Z0-9]', '', reason_desc)}"
                    reason_ind = get_or_create_individual(cls_OperationalReason, reason_name, onto, extra_label=reason_desc)
                    if reason_ind:
                        # Set properties if not already set
                        if prop_reasonDescription and not reason_ind.reasonDescription:
                            reason_ind.reasonDescription = [reason_desc]
                        # Alt lang needs locstr handling - assuming plain string for now
                        alt_reason = safe_cast(row.get('UTIL_ALT_LANGUAGE_REASON'), str)
                        if prop_altReasonDescription and alt_reason and not reason_ind.altReasonDescription:
                            # Here you could potentially create locstr if language info was available
                            reason_ind.altReasonDescription = [alt_reason] # or [locstr(alt_reason, lang="xx")]
                        dt_driver = safe_cast(row.get('DOWNTIME_DRIVER'), str)
                        if prop_downtimeDriver and dt_driver and not reason_ind.downtimeDriver:
                            reason_ind.downtimeDriver = [dt_driver]
                        # Handle combined CO_TYPE columns
                        co_type = safe_cast(row.get('CO_TYPE'), str) or safe_cast(row.get('CO_ORIGINAL_TYPE'), str)
                        if prop_changeoverType and co_type and not reason_ind.changeoverType:
                            reason_ind.changeoverType = [co_type]


                # --- Create Time Interval ---
                start_time = safe_cast(row.get('JOB_START_TIME_LOC'), datetime)
                end_time = safe_cast(row.get('JOB_END_TIME_LOC'), datetime)
                time_interval_ind = None
                if start_time and cls_TimeInterval:
                     # Create a unique TimeInterval for each event record
                     # Use start time and resource ID for uniqueness
                     res_id_part = eq_id_str if equipment_ind else line_id
                     interval_name = f"TimeInterval_{res_id_part}_{start_time.strftime('%Y%m%dT%H%M%S')}_{i}"
                     time_interval_ind = get_or_create_individual(cls_TimeInterval, interval_name, onto)
                     if time_interval_ind:
                          if prop_startTime: time_interval_ind.startTime = [start_time]
                          if prop_endTime and end_time: time_interval_ind.endTime = [end_time]
                          # Calculate duration? Spec doesn't require it directly on TimeInterval


                # --- Create Event Record Individual ---
                # Need a unique identifier for each event record (row)
                event_record_name = f"Event_{res_id_part}_{start_time.strftime('%Y%m%dT%H%M%S')}_{i}" if start_time else f"Event_{res_id_part}_{i}"
                event_ind = get_or_create_individual(cls_EventRecord, event_record_name, onto)

                if not event_ind:
                     logger.error(f"Row {i}: Failed to create EventRecord individual. Skipping row.")
                     continue

                # --- Populate EventRecord Properties ---
                if prop_operationType: event_ind.operationType = [safe_cast(row.get('OPERA_TYPE'), str)]
                if prop_rampUpFlag: event_ind.rampUpFlag = [safe_cast(row.get('RAMPUP_FLAG'), bool, default=False)] # Default to False if missing/invalid

                # Time Metrics
                total_time = safe_cast(row.get('TOTAL_TIME'), Decimal) # Minutes
                if prop_reportedDurationMinutes and total_time is not None:
                    event_ind.reportedDurationMinutes = [total_time]
                # else: # Try seconds if minutes is empty?
                #    total_time_sec = safe_cast(row.get('TOTAL_TIME_SECONDS'), Decimal)
                #    if prop_reportedDurationMinutes and total_time_sec is not None:
                #         event_ind.reportedDurationMinutes = [total_time_sec / Decimal(60)]


                if prop_businessExternalTimeMinutes: event_ind.businessExternalTimeMinutes = [safe_cast(row.get('BUSINESS_EXTERNAL_TIME'), Decimal)]
                if prop_plantAvailableTimeMinutes: event_ind.plantAvailableTimeMinutes = [safe_cast(row.get('PLANT_AVAILABLE_TIME'), Decimal)]
                if prop_effectiveRuntimeMinutes: event_ind.effectiveRuntimeMinutes = [safe_cast(row.get('EFFECTIVE_RUNTIME'), Decimal)]
                if prop_plantDecisionTimeMinutes: event_ind.plantDecisionTimeMinutes = [safe_cast(row.get('PLANT_DECISION_TIME'), Decimal)]
                if prop_productionAvailableTimeMinutes: event_ind.productionAvailableTimeMinutes = [safe_cast(row.get('PRODUCTION_AVAILABLE_TIME'), Decimal)]

                # --- Link EventRecord to other Individuals ---
                if prop_involvesResource and resource_individual: event_ind.involvesResource = [resource_individual]
                # Add links to ProdReq, Material, TimeInterval, Shift, State, Reason if properties defined
                # Need properties like 'associatedWithProductionRequest', 'usesMaterial', 'occursDuring', 'duringShift', 'eventHasState', 'eventHasReason'
                # if prop_associatedWithProductionRequest and req_ind: event_ind.associatedWithProductionRequest = [req_ind]
                # if prop_usesMaterial and mat_ind: event_ind.usesMaterial = [mat_ind]
                if prop_occursDuring and time_interval_ind: event_ind.occursDuring = [time_interval_ind]
                if prop_duringShift and shift_ind: event_ind.duringShift = [shift_ind]
                if prop_eventHasState and state_ind: event_ind.eventHasState = [state_ind]
                if prop_eventHasReason and reason_ind: event_ind.eventHasReason = [reason_ind]

                # Add links to Personnel, ProcessSegment if data/properties exist


                processed_ids.add(event_record_name) # Mark as processed


            except Exception as e:
                logger.error(f"Error processing data row {i}: {row}")
                logger.exception("Exception details:") # Log traceback for debugging

    logger.info(f"Ontology population complete. Processed {len(processed_ids)} unique event records.")


# Example usage (if run directly)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # --- Dummy Ontology Definition for Testing ---
    test_onto = get_ontology("http://example.com/test_ontology_population.owl")
    with test_onto:
         class Plant(Thing): pass
         class plantId(DataProperty, FunctionalProperty): range = [str]
         class Area(Thing): pass
         class areaId(DataProperty, FunctionalProperty): range = [str]
         class ProcessCell(Thing): pass
         class processCellId(DataProperty, FunctionalProperty): range = [str]
         class ProductionLine(Thing): pass
         class lineId(DataProperty, FunctionalProperty): range = [str]
         class Equipment(Thing): pass
         class equipmentId(DataProperty, FunctionalProperty): range = [str]
         class equipmentName(DataProperty): range = [str]
         class equipmentModel(DataProperty): range = [str]
         class complexity(DataProperty): range = [str]
         class alternativeModel(DataProperty): range = [str]
         class EquipmentClass(Thing): pass
         class equipmentClassId(DataProperty, FunctionalProperty): range = [str]
         class memberOfClass(ObjectProperty): domain=[Equipment]; range=[EquipmentClass]
         class Material(Thing): pass
         class materialId(DataProperty, FunctionalProperty): range = [str]
         class materialDescription(DataProperty): range = [str]
         class sizeType(DataProperty): range = [str]
         class materialUOM(DataProperty): range = [str]
         class standardUOM(DataProperty): range = [str]
         class targetProductUOM(DataProperty): range = [str]
         class conversionFactor(DataProperty): range = [Decimal]
         class ProductionRequest(Thing): pass
         class requestId(DataProperty, FunctionalProperty): range = [str]
         class requestDescription(DataProperty): range = [str]
         class requestRate(DataProperty): range = [Decimal]
         class requestRateUOM(DataProperty): range = [str]
         class TimeInterval(Thing): pass
         class startTime(DataProperty, FunctionalProperty): range = [datetime]
         class endTime(DataProperty, FunctionalProperty): range = [datetime]
         class Shift(Thing): pass
         class shiftId(DataProperty, FunctionalProperty): range = [str]
         class shiftStartTime(DataProperty, FunctionalProperty): range = [datetime]
         class shiftEndTime(DataProperty, FunctionalProperty): range = [datetime]
         class shiftDurationMinutes(DataProperty, FunctionalProperty): range = [Decimal]
         class EventRecord(Thing): pass
         class involvesResource(ObjectProperty): range=[ProductionLine | Equipment] # Example range union
         class occursDuring(ObjectProperty): range=[TimeInterval]
         class duringShift(ObjectProperty): range=[Shift]
         class eventHasState(ObjectProperty): range=[OperationalState]
         class eventHasReason(ObjectProperty): range=[OperationalReason]

         class operationType(DataProperty): range = [str]
         class rampUpFlag(DataProperty): range = [bool]
         class reportedDurationMinutes(DataProperty, FunctionalProperty): range = [Decimal]
         class businessExternalTimeMinutes(DataProperty, FunctionalProperty): range = [Decimal]
         class plantAvailableTimeMinutes(DataProperty, FunctionalProperty): range = [Decimal]
         class effectiveRuntimeMinutes(DataProperty, FunctionalProperty): range = [Decimal]
         class plantDecisionTimeMinutes(DataProperty, FunctionalProperty): range = [Decimal]
         class productionAvailableTimeMinutes(DataProperty, FunctionalProperty): range = [Decimal]

         class OperationalState(Thing): pass
         class stateDescription(DataProperty): range = [str]
         class OperationalReason(Thing): pass
         class reasonDescription(DataProperty): range = [str]
         class altReasonDescription(DataProperty): range = [str]
         class downtimeDriver(DataProperty): range = [str]
         class changeoverType(DataProperty): range = [str]

    # Map names to classes/properties for the population function
    d_classes = {c.name: c for c in test_onto.classes()}
    d_props = {p.name: p for p in test_onto.properties()}

    # --- Load Sample Data ---
    data_path = 'sample_data.csv' # Replace with your actual data file path
    data = []
    try:
        with open(data_path, mode='r', encoding='utf-8') as infile:
             reader = csv.DictReader(infile)
             # Read only a few rows for testing
             for i, row in enumerate(reader):
                 if i < 10: # Limit rows for testing
                    data.append(row)
                 else:
                     break
        logger.info(f"Loaded {len(data)} sample data rows for testing.")
    except FileNotFoundError:
        logger.error(f"Sample data file not found: {data_path}")
    except Exception as e:
        logger.error(f"Error reading sample data file {data_path}: {e}")

    # --- Populate ---
    if data:
         populate_ontology_from_data(test_onto, data, d_classes, d_props)

         # --- Verify Population (Basic Checks) ---
         print("\n--- Verification ---")
         print(f"Number of Event Records created: {len(list(test_onto.EventRecord.instances()))}")
         print(f"Number of Equipment created: {len(list(test_onto.Equipment.instances()))}")
         print(f"Number of Equipment Classes created: {len(list(test_onto.EquipmentClass.instances()))}")
         print(f"Number of Time Intervals created: {len(list(test_onto.TimeInterval.instances()))}")

         # Example: Find one event record and check properties
         if list(test_onto.EventRecord.instances()):
             ev = list(test_onto.EventRecord.instances())[0]
             print(f"\nExample Event Record: {ev.name}")
             if ev.reportedDurationMinutes: print(f"  Reported Duration: {ev.reportedDurationMinutes[0]} min")
             if ev.involvesResource: print(f"  Involves Resource: {ev.involvesResource[0].name}")
             if ev.occursDuring: print(f"  Occurs During: {ev.occursDuring[0].name}")
             if ev.occursDuring and ev.occursDuring[0].startTime: print(f"    Start Time: {ev.occursDuring[0].startTime[0]}")


         # Optionally save the test ontology
         # test_onto.save(file="test_populated_ontology.owl", format="rdfxml")
         # logger.info("Saved test populated ontology to test_populated_ontology.owl")