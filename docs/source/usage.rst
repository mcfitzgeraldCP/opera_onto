Usage Guide
===========

Basic Usage
===========

Command Line Usage
=================
Generate an ontology from a specification file and data file:

.. code-block:: bash

   python -m ontology_generator.main path/to/specification.csv path/to/data.csv path/to/output.owl

For example:

.. code-block:: bash

   python -m ontology_generator.main Ontology_specifications/OPERA_ISA95_OWL_ONT_V27.csv Data/mx_toothpaste_finishing_sample_100lines.csv test.owl

Additional options:

.. code-block:: bash

   python -m ontology_generator.main path/to/specification.csv path/to/data.csv path/to/output.owl --reasoner --optimize --verbose

Python API Usage
================
Here's a basic example of using the ontology generator in your Python code:

.. code-block:: python

   from ontology_generator.main import main_ontology_generation
   
   # Generate the ontology using the main generation function
   success = main_ontology_generation(
       spec_file_path="Ontology_specifications/OPERA_ISA95_OWL_ONT_V27.csv",
       data_file_path="Data/manufacturing_data.csv",
       output_owl_path="output.owl",
       ontology_iri="http://example.org/ontology.owl",
       save_format="rdfxml",
       use_reasoner=True
   )
   
   if success:
       print("Ontology generation completed successfully")
   else:
       print("Ontology generation encountered errors")

Configuration
=============
The generator can be configured using various command-line options or through the Python API.
See the :doc:`api/config` documentation for detailed configuration options.

Available command-line options:

.. code-block:: bash

   python -m ontology_generator.main --help

   # Output:
   # usage: main.py [-h] [--iri IRI] [--format {rdfxml,ntriples,nquads,owlxml}]
   #                [--reasoner] [--worlddb WORLDDB]
   #                [--max-report-entities MAX_REPORT_ENTITIES] [--full-report]
   #                [--no-analyze-population] [--strict-adherence]
   #                [--skip-classes SKIP_CLASSES [SKIP_CLASSES ...]] [--optimize]
   #                [--test-mappings] [--analyze-sequences OWL_FILE]
   #                [--event-buffer MINUTES] [-v] [-q]
   #                spec_file data_file output_file

Examples
========

Command Line Example
-------------------
Basic ontology generation:

.. code-block:: bash

   python -m ontology_generator.main Ontology_specifications/OPERA_ISA95_OWL_ONT_V27.csv Data/manufacturing_data.csv output.owl

With additional options:

.. code-block:: bash

   python -m ontology_generator.main Ontology_specifications/OPERA_ISA95_OWL_ONT_V27.csv Data/manufacturing_data.csv output.owl --reasoner --optimize --iri "http://example.org/manufacturing#"

Python API Example
-----------------
.. code-block:: python

   from ontology_generator.main import main_ontology_generation
   import os
   
   # Define file paths
   spec_file = "Ontology_specifications/OPERA_ISA95_OWL_ONT_V27.csv"
   data_file = "Data/manufacturing_data.csv"
   output_file = "manufacturing.owl"
   
   # Generate the ontology with additional options
   success = main_ontology_generation(
       spec_file_path=spec_file,
       data_file_path=data_file,
       output_owl_path=output_file,
       ontology_iri="http://manufacturing.example.org/ontology#",
       save_format="rdfxml",
       use_reasoner=True,
       analyze_population=True,
       optimize_ontology=True,
       event_buffer_minutes=5
   )
   
   if success:
       print(f"Ontology successfully generated at {os.path.abspath(output_file)}")
   else:
       print("Ontology generation encountered errors") 