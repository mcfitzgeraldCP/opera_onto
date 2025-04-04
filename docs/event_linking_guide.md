# Event Linking in Ontology Generator

## Overview

Event linking is a critical process in the ontology generator that creates relationships between equipment-level events and their corresponding line-level events. This hierarchical connection allows for:

1. Tracing equipment events to their parent line events
2. Analyzing production issues across different levels of abstraction
3. Providing context for equipment failures within larger line operations

## How Event Linking Works

The linking process connects `EventRecord` individuals based on:

1. **Line Association**: Equipment must be associated with a line via the `isPartOfProductionLine` property
2. **Temporal Matching**: Events are linked based on time overlaps between equipment events and line events

### Temporal Matching Logic

When linking events, the system uses several matching strategies (in order of priority):

1. **Strict Containment**: Equipment event's start and end times fall completely within a line event's timeframe
2. **Start Containment**: Equipment event's start time falls within a line event's timeframe
3. **End Containment**: Equipment event's end time falls within a line event's timeframe
4. **Temporal Overlap**: Equipment event overlaps with a line event in any way

## Event Buffer Parameter

One of the most important parameters that affects event linking success is the **event buffer**.

### What is the Event Buffer?

The event buffer is a time window (in minutes) that allows events to be linked even if they don't exactly match temporally. The buffer creates flexibility in the matching process to account for:

- Clock synchronization issues between equipment
- Minor timing discrepancies in data recording
- Practical realities of production environment timing

### Default Configuration

The default event buffer is configured to **5 minutes** (set in `config.py` as `DEFAULT_EVENT_LINKING_BUFFER_MINUTES`). 

### When to Adjust the Event Buffer

You may need to adjust the event buffer in the following situations:

1. **High failure rate with `time_gap_too_large` errors**: This indicates events are nearby but outside the current buffer window
2. **Working with sparse data samples**: Small sample data may have larger temporal gaps than a complete dataset
3. **Equipment with known timing differences**: Some manufacturing environments have equipment with deliberately staggered starts/stops

### How to Adjust the Event Buffer

The event buffer can be adjusted using the command-line parameter `--event-buffer`:

```bash
python -m ontology_generator.main my_spec.csv my_data.csv output.owl --event-buffer 10
```

This example sets a 10-minute buffer for event linking, which would be useful for:
- Datasets with known timing gaps
- Test/sample datasets where events are temporally distant
- Initial analysis to determine appropriate buffer size

## Diagnosing Event Linking Issues

When event linking fails, detailed diagnostics are provided in the log output, including:

- **Failure breakdown**: Categories of failures (`no_line_events`, `time_gap_too_large`, etc.)
- **Near miss analysis**: Information about events that nearly qualified for linking
- **Suggested buffer adjustments**: Based on the gap analysis

### Common Failure Categories

1. **no_line_events (most common)**: No line-level events exist for the line that the equipment is associated with
   - *Solution*: Verify your data contains line-level events for all relevant lines
   - *Solution*: When using sample data, ensure it includes both equipment and corresponding line events

2. **time_gap_too_large**: Events are found but the temporal gap exceeds the buffer
   - *Solution*: Increase the event buffer using the `--event-buffer` parameter
   - *Solution*: For sample data with large time gaps, a larger buffer may be necessary

3. **equipment_outside_range**: Equipment events fall completely outside any line event timeframe
   - *Solution*: Check data consistency and event recording processes
   - *Solution*: May require domain-specific adjustments based on process understanding

## Best Practices

1. **Start with default buffer** for production data
2. **Increase buffer for sample datasets** where events may be more sparsely distributed
3. **Analyze failure reports** to determine appropriate buffer size
4. **Document your chosen buffer value** for production applications
5. **Consider process-specific timing** when determining buffer size

## Example: Adjusting Buffer Based on Failure Analysis

If you see output like this:

```
=== EVENT LINKING RESULTS ===
Failed to link: 23 (28.4%)
Failure breakdown:
  • no_line_events: 19 (82.6%)
  • time_gap_too_large: 4 (17.4%)
```

You should:
1. For `no_line_events` - Ensure your dataset includes line events for all referenced lines
2. For `time_gap_too_large` - Try increasing the buffer:
   ```bash
   python -m ontology_generator.main my_spec.csv my_data.csv output.owl --event-buffer 15
   ```

## Conclusion

The event buffer parameter is a key configuration option when working with temporal data in manufacturing environments. Adjusting it appropriately based on your specific dataset and process timing characteristics can significantly improve the quality of your generated ontology. 