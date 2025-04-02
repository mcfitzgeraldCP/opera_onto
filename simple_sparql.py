#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple SPARQL Query Runner for OWL ontologies using Owlready2
Usage: python simple_sparql.py test.owl
"""

from owlready2 import *
import sys

# Check command line arguments
if len(sys.argv) < 2:
    print("Usage: python simple_sparql.py <ontology_file>")
    sys.exit(1)

# Get ontology file from command line
ontology_file = sys.argv[1]

# Load the ontology
print(f"Loading ontology from {ontology_file}...")
try:
    onto = get_ontology(ontology_file).load()
    print(f"Successfully loaded ontology: {onto.base_iri}")
except Exception as e:
    print(f"Error loading ontology: {e}")
    sys.exit(1)

# Create RDFlib graph
graph = onto.world.as_rdflib_graph()

# PASTE YOUR SPARQL QUERY HERE
query = """
PREFIX onto: <http://example.com/manufacturing_ontology.owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?individual 
WHERE {
    ?individual rdf:type onto:Area .
}
LIMIT 10
"""

# Execute the query
print(f"\nExecuting SPARQL query:\n{query}\n")
try:
    results = list(graph.query_owlready(query))
    
    if not results:
        print("No results found.")
    else:
        print(f"Found {len(results)} results:")
        
        # Process and display results
        for i, result in enumerate(results):
            if hasattr(result, "__iter__") and not isinstance(result, str):
                print(f"Result {i+1}: {' | '.join(str(item) for item in result)}")
            else:
                print(f"Result {i+1}: {result}")
            
except Exception as e:
    print(f"Error executing query: {e}") 