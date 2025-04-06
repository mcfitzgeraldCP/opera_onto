Welcome to Opera Ontology Generator's documentation!
===================================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   usage
   api/index

Introduction
-----------
The Opera Ontology Generator is a tool for generating and managing ontologies, 
providing functionality for ontology creation, population, and analysis.

Quick Start
----------
.. code-block:: bash

   # Install the package
   pip install .

   # Run the ontology generator
   python -m ontology_generator.main Ontology_specifications/OPERA_ISA95_OWL_ONT_V27.csv Data/mx_toothpaste_finishing_sample_100lines.csv test.owl
   
   # For help with options
   python -m ontology_generator.main --help

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search` 