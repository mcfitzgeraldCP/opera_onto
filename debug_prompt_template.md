# Ontology Code Debug Assistant Prompt

## Task Description
You are tasked with helping debug the ontology generation code based on the provided source code and log files (especially WARNING messages). 
Please analyze the warnings, errors, and potential issues in the implementation. After explaining your analysis, provide a 
prompt that can be fed to an agent to make the proposed fixes. Ask for confirmation if unclear or there are multiple options. Confirm that you understand.

## Instructions
1. Review the code and logs provided below
2. Identify potential issues, bugs, and areas for improvement
3. Suggest specific fixes and improvements
4. Feel free to ask for additional information such as:
   - owlready2 documentation
   - Specific error messages or stack traces
   - Sample data structures
   - Related ontology concepts

## Available Resources
- Full source code of create_ontology.py
- Execution logs from Logs/log.txt
- Ontology specification (OPERA_ISA95_OWL_ONT_V6.csv)
- Sample data (mx_toothpaste_finishing_sample_100lines.csv)
- Access to owlready2 documentation if needed

## Ontology Specification
```csv
<SPEC_CONTENT>
```

## Sample Data
```csv
<SAMPLE_CONTENT>
```

## Code and Logs

### Source Code: create_ontology.py
```python
<CODE_CONTENT>
```

### Execution Logs: Logs/log.txt
```
<LOG_CONTENT>
```

## Questions
1. What specific issues do you notice in the code or logs?
2. What additional information would help in debugging these issues?
3. What improvements would you suggest to make the code more robust?

