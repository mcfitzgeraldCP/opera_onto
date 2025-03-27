"""Classes for the manufacturing ontology."""

# Import all classes from submodules
from ontology.classes.assets import *
from ontology.classes.location import *
from ontology.classes.organizational import *
from ontology.classes.process import *
from ontology.classes.time_related import *
from ontology.classes.events import *
from ontology.classes.utilization import *

# Add all class names to __all__
__all__ = [
    # Assets
    "ManufacturingAsset",
    "Plant",
    "Line",
    "Equipment",
    # Location
    "Location",
    "Country",
    "StrategicLocation",
    "PhysicalArea",
    # Organizational
    "OrganizationalUnit",
    "Division",
    "SubDivision",
    "FocusFactory",
    "GlobalHierarchyArea",
    "GlobalHierarchyCategory",
    "PurchasingOrganization",
    # Process
    "ProcessContext",
    "Material",
    "ProductionOrder",
    "Crew",
    # Time-related
    "TimeRelated",
    "TimeInterval",
    "Shift",
    # Events
    "EventRecord",
    # Utilization
    "UtilizationState",
    "UtilizationReason",
    "DowntimeState",
    "RunningState",
    "WaitingState",
    "PlannedStopState",
    "ChangeoverState",
    "BusinessExternalState",
    "UnknownState",
    "MaintenanceReason",
    "PlannedMaintenanceReason",
    "AutonomousMaintenanceReason",
    "UnplannedMaintenanceReason",
    "ChangeoverReason",
    "WaitingReason",
    "OperationalReason",
    "ExternalReason",
    "QualityLossReason",
    "SpeedLossReason",
    "ProcessReason",
    "ExperimentationReason",
    "CleaningSanitationReason",
]
