#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SPARQL Query Runner for test.owl ontology using Owlready2
"""

from owlready2 import *
import os

def load_ontology(file_path):
    """Load the ontology file"""
    print(f"Loading ontology from {file_path}...")
    
    if os.path.exists(file_path):
        # Load the ontology
        onto = get_ontology(file_path).load()
        print(f"Successfully loaded ontology: {onto.base_iri}")
        return onto
    else:
        print(f"Error: File {file_path} not found.")
        return None

def run_query(graph, query, convert_to_owlready=True):
    """Run a SPARQL query and return the results"""
    print(f"\nExecuting SPARQL query:\n{query}\n")
    
    try:
        if convert_to_owlready:
            results = list(graph.query_owlready(query))
        else:
            results = list(graph.query(query))
        
        return results
    except Exception as e:
        print(f"Error running query: {e}")
        return []

def print_results(results):
    """Print the query results in a formatted way"""
    if not results:
        print("No results found.")
        return
    
    print(f"Found {len(results)} results:")
    
    # Get column names from the first result
    if hasattr(results[0], "__iter__") and not isinstance(results[0], str):
        if hasattr(results[0], "_fields"):  # Named tuple
            headers = results[0]._fields
        else:
            headers = [f"Column {i+1}" for i in range(len(results[0]))]
            
        # Print headers
        header_str = " | ".join(str(h) for h in headers)
        print("-" * len(header_str))
        print(header_str)
        print("-" * len(header_str))
        
        # Print rows
        for row in results:
            print(" | ".join(str(item) for item in row))
    else:
        # Single column results
        for row in results:
            print(row)
    
    print("-" * 50)

def run_example_queries(onto):
    """Run the example queries from ont_guide.txt"""
    # Create RDFlib graph from the ontology
    graph = onto.world.as_rdflib_graph()
    
    # Query 1: List individuals of a class (Area)
    query1 = """
    PREFIX onto: <http://example.com/manufacturing_ontology.owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?individual 
    WHERE {
        ?individual rdf:type onto:Area .
    }
    LIMIT 10
    """
    results1 = run_query(graph, query1)
    print("Query 1: List individuals of Area class")
    print_results(results1)
    
    # Query 2: Query by object property
    query2 = """
    PREFIX onto: <http://example.com/manufacturing_ontology.owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?subject ?object
    WHERE {
        ?subject rdf:type onto:Area .
        ?object rdf:type onto:ProcessCell .
        ?subject onto:hasProcessCell ?object .
    }
    LIMIT 10
    """
    results2 = run_query(graph, query2)
    print("Query 2: Find Areas and their ProcessCells")
    print_results(results2)
    
    # Query 3: Query by data property
    query3 = """
    PREFIX onto: <http://example.com/manufacturing_ontology.owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?individual ?value
    WHERE {
        ?individual rdf:type onto:EventRecord .
        ?individual onto:aeModelCategory ?value .
    }
    LIMIT 10
    """
    results3 = run_query(graph, query3)
    print("Query 3: Find EventRecords with their aeModelCategory values")
    print_results(results3)
    
    # Query 4: Complex query
    query4 = """
    PREFIX onto: <http://example.com/manufacturing_ontology.owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?individual1 ?individual2
    WHERE {
        ?individual1 rdf:type onto:Area .
        ?individual2 rdf:type onto:ProcessCell .
        ?individual1 onto:hasProcessCell ?individual2 .
    }
    LIMIT 10
    """
    results4 = run_query(graph, query4)
    print("Query 4: Complex query finding Areas and their ProcessCells")
    print_results(results4)

def run_custom_query(onto, query_string):
    """Run a custom SPARQL query provided by the user"""
    graph = onto.world.as_rdflib_graph()
    results = run_query(graph, query_string)
    print("Custom Query Results:")
    print_results(results)

def main():
    """Main function to run the script"""
    # Path to the ontology file
    ontology_file = "test.owl"
    
    # Load the ontology
    onto = load_ontology(ontology_file)
    
    if onto is None:
        return
    
    # Run the example queries
    run_example_queries(onto)
    
    # Option to run a custom query
    print("\nWould you like to run a custom SPARQL query? (y/n)")
    choice = input().strip().lower()
    
    if choice == 'y':
        print("Enter your SPARQL query (end with a blank line):")
        query_lines = []
        while True:
            line = input()
            if line.strip() == "":
                break
            query_lines.append(line)
        
        custom_query = "\n".join(query_lines)
        if custom_query:
            run_custom_query(onto, custom_query)
    
    print("SPARQL query execution completed.")

if __name__ == "__main__":
    main() 