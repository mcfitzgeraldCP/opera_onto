
Please debug and revise the ontology specification to address the following issues. Reference the ISA95 standard for the recommended class hierarchy.

Major Issue: Missing Parent Class Column in Spec:
Code: The define_ontology_structure function explicitly looks for a column named Parent Class (defined by SPEC_PARENT_CLASS_COLUMN = 'Parent Class') in the specification CSV to build the class hierarchy (subclassOf relationships).
Specification: The provided snippet of OPERA_ISA95_OWL_ONT_V5.csv does not contain a Parent Class column.
Impact: The class hierarchy logic in define_ontology_structure will likely fail to establish any parent-child relationships beyond making every class a direct subclass of owl:Thing. This significantly deviates from a potentially intended hierarchical structure. The code might run without error if the column is simply missing (due to .get(SPEC_PARENT_CLASS_COLUMN, '')), but the resulting ontology structure will be flat.

onfirmation of Parent Class Column: Does the full specification CSV actually contain a Parent Class column? If not, how should hierarchy be determined (if at all)?

## Ontology Specification
```csv
Logical Group,Raw Data Column Name,Proposed OWL Entity,Proposed OWL Property,OWL Property Type,Target/Range (xsd:) / Target Class,OWL Property Characteristics,Inverse Property,Domain,Property Restrictions,ISA-95 Concept,Notes/Considerations
Asset Hierarchy,PLANT,Plant,plantId,DatatypeProperty,xsd:string,Functional,,Plant,,Enterprise/Site ID,Used to create/identify Plant Individual - harmonized with B2MML terminology.
Asset Hierarchy,GH_FOCUSFACTORY,Area,areaId,DatatypeProperty,xsd:string,Functional,,Area,,Area ID,Used to create/identify Area Individual. Links via locatedInPlant to Plant.
Asset Hierarchy,PHYSICAL_AREA,ProcessCell,processCellId,DatatypeProperty,xsd:string,Functional,,ProcessCell,,Area/ProcessCell ID,Links via partOfArea to Area.
Asset Hierarchy,LINE_NAME,ProductionLine,lineId,DatatypeProperty,xsd:string,Functional,,ProductionLine,,ProductionLine/ProcessCell ID,Links via locatedInProcessCell to ProcessCell.
Asset Hierarchy,EQUIPMENT_ID,Equipment,equipmentId,DatatypeProperty,xsd:string,Functional,,Equipment,,Equipment ID,Preferred ID for Equipment Individual. Links via isPartOfProductionLine to ProductionLine.
Asset Hierarchy,EQUIPMENT_NAME,Equipment,equipmentName,DatatypeProperty,xsd:string,-,,Equipment,,Equipment Description,Secondary ID. Used to determine EquipmentClass. Consider rdfs:label.
Asset Hierarchy,EQUIPMENT_TYPE,EventRecord,involvesResource,ObjectProperty,ProductionLine | Equipment,,isInvolvedIn,ProcessSegment,min 1,SegmentResponse Resource,Maps to Operations Record Information (Section 5.10). Define inverse? (e.g. resourceInvolvedIn)
Asset Hierarchy,N/A,Area,locatedInPlant,ObjectProperty,Plant,-,hasArea,Area,,Hierarchy Scope,Links an Area to the Plant it resides in.
Asset Hierarchy,N/A,ProcessCell,partOfArea,ObjectProperty,Area,-,hasProcessCell,ProcessCell,,Hierarchy Scope,Links a ProcessCell to the Area it is part of.
Asset Hierarchy,N/A,ProductionLine,locatedInProcessCell,ObjectProperty,ProcessCell,-,containsProductionLine,ProductionLine,,Hierarchy Scope,Links a ProductionLine to the ProcessCell it resides in.
Asset Hierarchy,N/A,Equipment,isPartOfProductionLine,ObjectProperty,ProductionLine,-,hasEquipmentPart,Equipment,,Hierarchy Scope,Links an Equipment instance to the ProductionLine it is part of.
Equipment Attributes,EQUIPMENT_MODEL,Equipment,equipmentModel,DatatypeProperty,xsd:string,Functional,,Equipment,,Equipment Property/Model,Property of Equipment according to Section 5.5.
Equipment Attributes,COMPLEXITY,Equipment,complexity,DatatypeProperty,xsd:string,-,,Equipment,,Equipment Property,Property of Equipment according to Section 5.5.
Equipment Attributes,MODEL,Equipment,alternativeModel,DatatypeProperty,xsd:string,-,,Equipment,,Equipment Property,Property of Equipment according to Section 5.5.
Equipment Capability,N/A,EquipmentCapability,capabilityType,DatatypeProperty,xsd:string,Functional,,EquipmentCapability,,Operations Capability,Added for Section 6.4 Operations Capability. Identifier for the capability type.
Equipment Capability,N/A,Equipment,hasCapability,ObjectProperty,EquipmentCapability,,isCapabilityOf,Equipment,,Operations Capability,Links Equipment to capabilities per Section 6.4. Define inverse? (e.g. capabilityOf)
Equipment Class,EQUIPMENT_NAME (parsed),EquipmentClass,equipmentClassId,DatatypeProperty,xsd:string,Functional,,EquipmentClass,,EquipmentClass ID,Parse from EQUIPMENT_NAME to create appropriate EquipmentClass.
Equipment Class,N/A,Equipment,memberOfClass,ObjectProperty,EquipmentClass,Functional,hasInstance,Equipment,,EquipmentClass Hierarchy,Links Equipment instances to their EquipmentClass. Define inverse? (e.g. classMember)
Equipment Sequence,N/A,EquipmentClass,isUpstreamOf,ObjectProperty,EquipmentClass,"Transitive, Asymmetric",isDownstreamOf,EquipmentClass,,Equipment Hierarchy/Topology,Defines upstream relationship between equipment classes. Needs inverseOf: isDownstreamOf
Equipment Sequence,N/A,EquipmentClass,isDownstreamOf,ObjectProperty,EquipmentClass,"Transitive, Asymmetric",isUpstreamOf,EquipmentClass,,Equipment Hierarchy/Topology,Defines downstream relationship between equipment classes.
Equipment Sequence,N/A,EquipmentClass,isParallelWith,ObjectProperty,EquipmentClass,"Symmetric, Irreflexive",,EquipmentClass,,Equipment Hierarchy/Topology,Defines equipment classes that operate in parallel.
Equipment Sequence,N/A,EquipmentClass,defaultSequencePosition,DatatypeProperty,xsd:integer,Functional,,EquipmentClass,,Equipment Hierarchy/Topology,Optional numerical position in default sequence (1-based). Functional per class in sequence context.
Equipment Sequence,N/A,Equipment,isUpstreamOf,ObjectProperty,Equipment,"Transitive, Asymmetric",isDownstreamOf,Equipment,,Equipment Hierarchy Instance,Instance-level relationship. Needs inverseOf: isDownstreamOf. Transitivity often inferred/applied via class or sequence logic.
Equipment Sequence,N/A,Equipment,isDownstreamOf,ObjectProperty,Equipment,"Transitive, Asymmetric",isUpstreamOf,Equipment,,Equipment Hierarchy Instance,Instance-level relationship. Transitivity often inferred/applied via class or sequence logic.
Equipment Sequence,N/A,Equipment,isParallelWith,ObjectProperty,Equipment,"Symmetric, Irreflexive",,Equipment,,Equipment Hierarchy Instance,Instance-level relationship. Mirrors class property.
Equipment Sequence,N/A,Equipment,actualSequencePosition,DatatypeProperty,xsd:integer,Functional,,Equipment,,Equipment Hierarchy Instance,Actual position in sequence for this specific line configuration. Functional per equipment instance in sequence.
Equipment Sequence,N/A,ProductionLine,hasSequenceDefinition,ObjectProperty,SequenceDefinition,-,,ProductionLine,,Equipment Hierarchy Context,Links a line to its defined equipment sequence. Define inverse? (e.g. sequenceForLine)
Equipment Sequence,N/A,SequenceDefinition,sequenceId,DatatypeProperty,xsd:string,Functional,,SequenceDefinition,,Equipment Hierarchy Context,Unique identifier for a sequence definition.
Equipment Sequence,N/A,SequenceDefinition,sequenceDescription,DatatypeProperty,xsd:string,-,,SequenceDefinition,,Equipment Hierarchy Context,Description of the sequence purpose/configuration.
Equipment Sequence,N/A,SequenceSegment,segmentId,DatatypeProperty,xsd:string,Functional,,SequenceSegment,,Process Segment Sequence,Unique identifier for a sequence segment within a sequence.
Equipment Sequence,N/A,SequenceSegment,previousSegment,ObjectProperty,SequenceSegment,"Functional, Asymmetric",nextSegment,SequenceSegment,,Process Segment Sequence,Links to previous segment. Functional assumes simple linear sequence for this direct link.
Equipment Sequence,N/A,SequenceSegment,nextSegment,ObjectProperty,SequenceSegment,"Functional, Asymmetric",previousSegment,SequenceSegment,,Process Segment Sequence,Links to next segment. Functional assumes simple linear sequence for this direct link.
Equipment Sequence,N/A,SequenceSegment,hasParallelPaths,ObjectProperty,SequenceSegment,-,,SequenceSegment,,Process Segment Sequence,Links to parallel segments. Use for branching/joining. Define inverse
Material & Prod Order,MATERIAL_ID,Material,materialId,DatatypeProperty,xsd:string,Functional,,Material,,MaterialDefinition ID,Used to create/identify Material Individual per Section 5.7.
Material & Prod Order,SHORT_MATERIAL_ID,Material,materialDescription,DatatypeProperty,xsd:string,-,,Material,,MaterialDefinition Description,Property of Material per Section 5.7. Consider rdfs:comment.
Material & Prod Order,SIZE_TYPE,Material,sizeType,DatatypeProperty,xsd:string,-,,Material,,Material Property,Property of Material per Section 5.7.
Material & Prod Order,MATERIAL_UOM,Material,materialUOM,DatatypeProperty,xsd:string,Functional,,Material,,MaterialDefinition BaseUnitOfMeasure,Property of Material per Section 5.7. (Functional per Material instance)
Material & Prod Order,"UOM_ST, UOM_ST_SAP",Material,standardUOM,DatatypeProperty,xsd:string,Functional,,Material,,Material Property (UoM),Property of Material per Section 5.7. (Functional per Material instance)
Material & Prod Order,TP_UOM,Material,targetProductUOM,DatatypeProperty,xsd:string,Functional,,Material,,Material Property (UoM),Property of Material per Section 5.7. (Functional per Material instance)
Material & Prod Order,PRIMARY_CONV_FACTOR,Material,conversionFactor,DatatypeProperty,xsd:decimal,Functional,,Material,,Material Property,Property of Material per Section 5.7. (Functional per Material instance context)
Material & Prod Order,PRODUCTION_ORDER_ID,ProductionRequest,requestId,DatatypeProperty,xsd:string,Functional,,ProductionRequest,,OperationsRequest ID,Used to create/identify ProductionRequest per Section 6.1.
Material & Prod Order,PRODUCTION_ORDER_DESC,ProductionRequest,requestDescription,DatatypeProperty,xsd:string,-,,ProductionRequest,,OperationsRequest Desc,Property of ProductionRequest per Section 6.1.
Material & Prod Order,PRODUCTION_ORDER_RATE,ProductionRequest,requestRate,DatatypeProperty,xsd:decimal,Functional,,ProductionRequest,,OperationsRequest Prop,Property of ProductionRequest per Section 6.1. (Functional per Request instance)
Material & Prod Order,PRODUCTION_ORDER_UOM,ProductionRequest,requestRateUOM,DatatypeProperty,xsd:string,Functional,,ProductionRequest,,OperationsRequest Prop,Property of ProductionRequest per Section 6.1. (Functional per Request instance)
Operational Context,N/A,EventRecord,associatedWithProductionRequest,ObjectProperty,ProductionRequest,-,hasAssociatedEvent,EventRecord,,OperationsResponse Link,Links an EventRecord to the ProductionRequest it fulfills or relates to.
Operational Context,N/A,EventRecord,usesMaterial,ObjectProperty,Material,-,materialUsedIn,EventRecord,,OperationsSegment MaterialActual,Links an EventRecord (representing actual work) to the Material consumed or produced.
Operational Context,N/A,EventRecord,duringShift,ObjectProperty,Shift,Functional,includesEvent,EventRecord,,PersonnelSchedule Link,Links an EventRecord to the Shift during which it occurred.
Operational Context,N/A,EventRecord,eventHasState,ObjectProperty,OperationalState,Functional,stateOfEvent,EventRecord,,OperationsRecord State Link,Links an EventRecord to the OperationalState describing it.
Operational Context,N/A,EventRecord,eventHasReason,ObjectProperty,OperationalReason,Functional,reasonForEvent,EventRecord,,OperationsEvent Reason Link,Links an EventRecord to the OperationalReason explaining its state.
Performance Metrics,TOTAL_TIME,EventRecord,reportedDurationMinutes,DatatypeProperty,xsd:decimal,Functional,,EventRecord,,OperationsPerformance Duration,Property of EventRecord per Section 6.3. (Functional per EventRecord instance)
Performance Metrics,BUSINESS_EXTERNAL_TIME,EventRecord,businessExternalTimeMinutes,DatatypeProperty,xsd:decimal,Functional,,EventRecord,,OperationsPerformance Parameter,Property of EventRecord per Section 6.3. (Functional per EventRecord instance)
Performance Metrics,PLANT_AVAILABLE_TIME,EventRecord,plantAvailableTimeMinutes,DatatypeProperty,xsd:decimal,Functional,,EventRecord,,OperationsPerformance Parameter,Property of EventRecord per Section 6.3. (Functional per EventRecord instance)
Performance Metrics,EFFECTIVE_RUNTIME,EventRecord,effectiveRuntimeMinutes,DatatypeProperty,xsd:decimal,Functional,,EventRecord,,OperationsPerformance Parameter,Property of EventRecord per Section 6.3. (Functional per EventRecord instance)
Performance Metrics,PLANT_DECISION_TIME,EventRecord,plantDecisionTimeMinutes,DatatypeProperty,xsd:decimal,Functional,,EventRecord,,OperationsPerformance Parameter,Property of EventRecord per Section 6.3. (Functional per EventRecord instance)
Performance Metrics,PRODUCTION_AVAILABLE_TIME,EventRecord,productionAvailableTimeMinutes,DatatypeProperty,xsd:decimal,Functional,,EventRecord,,OperationsPerformance Parameter,Property of EventRecord per Section 6.3. (Functional per EventRecord instance)
Process Segments,N/A,ProcessSegment,segmentId,DatatypeProperty,xsd:string,Functional,,ProcessSegment,,ProcessSegment ID,Added for Section 5.8 Process Segment Information.
Process Segments,N/A,ProcessSegment,segmentDescription,DatatypeProperty,xsd:string,-,,ProcessSegment,,ProcessSegment Description,Property of ProcessSegment per Section 5.8.
Process Segments,N/A,EventRecord,implementsSegment,ObjectProperty,ProcessSegment,-,,EventRecord,,ProcessSegment Link,Links EventRecord to ProcessSegment per Section 5.8. Define inverse? (e.g. implementedByEvent)
Time & Schedule,JOB_START_TIME_LOC,TimeInterval,startTime,DatatypeProperty,xsd:dateTime,Functional,,TimeInterval,,SegmentResponse StartTime,EventRecord links via occursDuring to TimeInterval. (Functional per TimeInterval instance)
Time & Schedule,JOB_END_TIME_LOC,TimeInterval,endTime,DatatypeProperty,xsd:dateTime,Functional,,TimeInterval,,SegmentResponse EndTime,Part of the TimeInterval linked by EventRecord. (Functional per TimeInterval instance)
Time & Schedule,SHIFT_NAME,Shift,shiftId,DatatypeProperty,xsd:string,Functional,,Shift,,PersonnelSchedule ID,EventRecord links via duringShift to Shift.
Time & Schedule,SHIFT_START_DATE_LOC,Shift,shiftStartTime,DatatypeProperty,xsd:dateTime,Functional,,Shift,,PersonnelSchedule StartTime,Property of Shift per Personnel model. (Functional per Shift instance)
Time & Schedule,SHIFT_END_DATE_LOC,Shift,shiftEndTime,DatatypeProperty,xsd:dateTime,Functional,,Shift,,PersonnelSchedule EndTime,Property of Shift per Personnel model. (Functional per Shift instance)
Time & Schedule,SHIFT_DURATION_MIN,Shift,shiftDurationMinutes,DatatypeProperty,xsd:decimal,Functional,,Shift,,PersonnelSchedule Duration,Property of Shift per Personnel model. (Functional per Shift instance)
Time & Schedule,CREW_ID,PersonnelClass,personnelClassId,DatatypeProperty,xsd:string,Functional,,PersonnelClass,,PersonnelClass ID,Added to align with Section 5.4 Personnel model.
Time & Schedule,N/A,Person,personId,DatatypeProperty,xsd:string,Functional,,Person,,Person ID,Added for Section 5.4 Personnel model.
Time & Schedule,N/A,Person,memberOfPersonnelClass,ObjectProperty,PersonnelClass,-,,Person,,PersonnelClass Link,Links Person to PersonnelClass per Section 5.4. Define inverse? (e.g. personnelClassMember)
Time & Schedule,N/A,EventRecord,performedBy,ObjectProperty,Person,-,,EventRecord,,Personnel Link,Links EventRecord to Person per Section 5.4. Define inverse? (e.g.
Time & Schedule,RAMPUP_FLAG,EventRecord,rampUpFlag,DatatypeProperty,xsd:boolean,Functional,,EventRecord,,OperationsResponse Property,Property of EventRecord per Section 6.3. (Functional per EventRecord instance)
Time & Schedule,N/A,EventRecord,occursDuring,ObjectProperty,TimeInterval,Functional,,EventRecord,,SegmentResponse TimeInterval,Links EventRecord to TimeInterval. This property is essential for data population.
Transaction Elements,N/A,TransactionModel,transactionType,DatatypeProperty,xsd:string,-,,TransactionModel,,Transaction Type,Added for Section 3 Transaction Definitions.
Transaction Elements,N/A,TransactionModel,applicationArea,ObjectProperty,ApplicationArea,-,,TransactionModel,,Transaction Application Area,Added for Section 3.1.19 Standard Transaction Element Structure.
Transaction Elements,N/A,TransactionModel,dataArea,ObjectProperty,DataArea,-,,TransactionModel,,Transaction Data Area,Added for Section 3.1.19 Standard Transaction Element Structure.
Utilization State/Reason,UTIL_STATE_DESCRIPTION,OperationalState,stateDescription,DatatypeProperty,xsd:string,-,,OperationalState,,OperationsRecord State,Maps to Ops Record Information (Section 5.10). Consider linking EventRecord to OperationalState instance via ObjectProperty.
Utilization State/Reason,UTIL_REASON_DESCRIPTION,OperationalReason,reasonDescription,DatatypeProperty,xsd:string,-,,OperationalReason,,OperationsEvent Reason,Maps to Ops Event Information (Section 5.11). Consider linking EventRecord to OperationalReason instance via ObjectProperty.
Utilization State/Reason,UTIL_ALT_LANGUAGE_REASON,OperationalReason,altReasonDescription,DatatypeProperty,xsd:string (with lang tag),-,,OperationalReason,,OperationsEvent Description,Property of OperationalReason per Section 5.11.
Utilization State/Reason,DOWNTIME_DRIVER,OperationalReason,downtimeDriver,DatatypeProperty,xsd:string,-,,OperationalReason,,OperationsEvent Category,Property of OperationalReason per Section 5.11.
Utilization State/Reason,OPERA_TYPE,EventRecord,operationType,DatatypeProperty,xsd:string,-,,EventRecord,,OperationsRecord Type,Property of EventRecord per Section 5.10. Categorical.
Utilization State/Reason,"CO_TYPE, CO_ORIGINAL_TYPE",OperationalReason,changeoverType,DatatypeProperty,xsd:string,-,,OperationalReason,,OperationsEvent Detail,Property of OperationalReason for changeover events. Categorical.```
