Usage Guide
===========

Basic Usage
----------
The Opera Ontology Generator can be used from the command line or as a Python package.

Command Line Usage
----------------
Generate an ontology from a specification file:

.. code-block:: bash

   python -m ontology_generator.main --spec path/to/specification.csv --output path/to/output.owl

Python API Usage
--------------
Here's a basic example of using the ontology generator in your Python code:

.. code-block:: python

   from ontology_generator.main import populate_ontology_from_data
   from owlready2 import *

   # Create a new ontology
   world = World()
   onto = world.get_ontology("http://example.org/ontology.owl")

   # Load your data
   data_rows = [...]  # Your data rows
   specification = [...]  # Your specification

   # Populate the ontology
   populate_ontology_from_data(
       onto=onto,
       data_rows=data_rows,
       defined_classes={},
       defined_properties={},
       property_is_functional={},
       specification=specification
   )

   # Save the ontology
   onto.save(file="output.owl", format="rdfxml")

Configuration
------------
The generator can be configured using various command-line options or through the Python API.
See the :doc:`api/config` documentation for detailed configuration options.

Examples
--------
For more detailed examples, see the :doc:`examples` section. 