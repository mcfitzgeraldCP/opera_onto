"""Utilization state and reason class definitions."""

import owlready2 as owl
from ontology.core import onto

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:

    class UtilizationState(owl.Thing):
        """Base class for equipment utilization states."""

        pass

    class UtilizationReason(owl.Thing):
        """Base class for equipment utilization reasons."""

        pass

    # --- State Specializations ---
    class DowntimeState(UtilizationState):
        """Equipment is in downtime state."""

        pass

    class RunningState(UtilizationState):
        """Equipment is in running state."""

        pass

    class WaitingState(UtilizationState):
        """Equipment is in waiting state."""

        pass

    class PlannedStopState(UtilizationState):
        """Equipment is in planned stop state."""

        pass  # Covers planned maint, meetings etc.

    class ChangeoverState(UtilizationState):
        """Equipment is in changeover state."""

        pass  # Can overlap with Downtime or Planned

    class BusinessExternalState(UtilizationState):
        """Equipment is not running due to business or external reasons."""

        pass  # e.g., No Demand

    class UnknownState(UtilizationState):
        """Equipment state is unknown or not entered."""

        pass  # For NOT_ENTERED

    # --- Reason Specializations ---
    class MaintenanceReason(UtilizationReason):
        """Base class for maintenance-related reasons."""

        pass

    class PlannedMaintenanceReason(MaintenanceReason):
        """Planned maintenance reason."""

        pass

    class AutonomousMaintenanceReason(MaintenanceReason):
        """Autonomous maintenance reason."""

        pass

    class UnplannedMaintenanceReason(MaintenanceReason):
        """Unplanned maintenance (breakdown) reason."""

        pass  # For breakdowns not covered by PM/AM

    class ChangeoverReason(UtilizationReason):
        """Changeover-related reason."""

        pass

    class WaitingReason(UtilizationReason):
        """Waiting-related reason."""

        pass  # e.g., Waiting Material, Upstream

    class OperationalReason(UtilizationReason):
        """Operational-related reason."""

        pass  # e.g., Meetings, Training, Breaks

    class ExternalReason(UtilizationReason):
        """External-related reason."""

        pass  # e.g., No Demand

    class QualityLossReason(UtilizationReason):
        """Quality loss-related reason."""

        pass  # If applicable (data focuses on time)

    class SpeedLossReason(UtilizationReason):
        """Speed loss-related reason."""

        pass  # If applicable (data focuses on time)

    class ProcessReason(UtilizationReason):
        """Process-related reason."""

        pass  # e.g., Jams, adjustments not maint.

    class ExperimentationReason(UtilizationReason):
        """Experimentation-related reason."""

        pass

    class CleaningSanitationReason(UtilizationReason):
        """Cleaning and sanitation-related reason."""

        pass


# Export classes for easy import
__all__ = [
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
