#!/usr/bin/env python3
"""
OWL Ontology Analyzer

This script uses Owlready2 to load an OWL ontology file and analyze its structure.
It extracts and displays useful information like prefixes, classes, properties,
and relationships that can be used in queries.
"""

import os
import sys
from collections import defaultdict, Counter
import pandas as pd
from owlready2 import *

def load_ontology(file_path):
    """Load the ontology from the given file path."""
    print(f"Loading ontology from {file_path}...")
    try:
        # Set up Owlready2 to handle RDF/XML and OWL files
        onto_path.append(os.path.dirname(os.path.abspath(file_path)))
        world = World()
        onto = world.get_ontology(file_path).load()
        print(f"Successfully loaded ontology: {onto.base_iri}")
        return world, onto
    except Exception as e:
        print(f"Error loading ontology: {e}")
        sys.exit(1)

def get_namespaces(world, onto):
    """Get all namespaces from the world and ontology."""
    namespaces = {}
    
    # Get the base IRI from the ontology
    if onto.base_iri:
        # Extract a suitable prefix from the base IRI
        base_name = onto.name.lower() if hasattr(onto, "name") else "onto"
        namespaces[base_name] = onto.base_iri
    
    # Add namespaces for imported ontologies, if the attribute exists
    if hasattr(onto, "imported_ontologies"):
        for imported_onto in onto.imported_ontologies:
            if hasattr(imported_onto, "name") and imported_onto.base_iri:
                prefix = imported_onto.name.lower()
                namespaces[prefix] = imported_onto.base_iri
    
    # Add standard namespaces
    namespaces["rdf"] = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    namespaces["rdfs"] = "http://www.w3.org/2000/01/rdf-schema#"
    namespaces["owl"] = "http://www.w3.org/2002/07/owl#"
    namespaces["xsd"] = "http://www.w3.org/2001/XMLSchema#"
    
    return namespaces

def analyze_classes(onto):
    """Analyze classes in the ontology."""
    classes = list(onto.classes())
    
    # Count class hierarchy
    class_hierarchy = defaultdict(list)
    class_depth = {}
    class_children = defaultdict(list)
    
    # Build hierarchy relationships
    for cls in classes:
        parents = [p for p in cls.is_a if isinstance(p, ThingClass) and p != Thing]
        for parent in parents:
            class_hierarchy[parent].append(cls)
            class_children[parent.name].append(cls.name)
    
    # Calculate depth of each class in hierarchy
    def calculate_depth(cls, depth=0):
        if cls in class_depth:
            return
        class_depth[cls] = depth
        for child in class_hierarchy[cls]:
            calculate_depth(child, depth + 1)
    
    # Calculate depth starting from top-level classes
    for cls in classes:
        parents = [p for p in cls.is_a if isinstance(p, ThingClass)]
        if not parents or (len(parents) == 1 and parents[0] == Thing):
            calculate_depth(cls)
    
    # Count instances per class
    instances_by_class = {}
    for cls in classes:
        instances = list(cls.instances())
        instances_by_class[cls.name] = len(instances)
    
    return {
        "classes": classes,
        "class_count": len(classes),
        "class_hierarchy": class_hierarchy,
        "class_depth": class_depth,
        "class_children": class_children,
        "instances_by_class": instances_by_class
    }

def analyze_properties(onto):
    """Analyze properties in the ontology."""
    # Get all properties
    object_properties = list(onto.object_properties())
    data_properties = list(onto.data_properties())
    annotation_properties = list(onto.annotation_properties())
    
    # Analyze property characteristics
    property_characteristics = {}
    property_domains = {}
    property_ranges = {}
    property_inverse = {}
    
    # Helper function to safely check characteristics
    def has_characteristic(prop, char_type):
        # Check if the characteristic exists as a class in the prop's is_a list
        char_uri = f"http://www.w3.org/2002/07/owl#{char_type}Property"
        for parent in prop.is_a:
            if hasattr(parent, "iri") and parent.iri == char_uri:
                return True
        # Some versions of Owlready2 may have the characteristic as a direct attribute
        if hasattr(prop, char_type.lower()) and getattr(prop, char_type.lower()):
            return True
        return False
    
    # Analyze object properties
    for prop in object_properties:
        # Get characteristics
        characteristics = []
        characteristic_types = ["Functional", "InverseFunctional", "Transitive", 
                               "Symmetric", "Asymmetric", "Reflexive", "Irreflexive"]
        
        for char_type in characteristic_types:
            if has_characteristic(prop, char_type):
                characteristics.append(char_type)
        
        property_characteristics[prop.name] = characteristics
        
        # Get domains and ranges
        domains = []
        ranges = []
        
        if hasattr(prop, "domain") and prop.domain:
            domains = [d.name if hasattr(d, "name") else str(d) for d in prop.domain]
        
        if hasattr(prop, "range") and prop.range:
            ranges = [r.name if hasattr(r, "name") else str(r) for r in prop.range]
        
        property_domains[prop.name] = domains
        property_ranges[prop.name] = ranges
        
        # Get inverse properties - safely check if inverse property exists
        if hasattr(prop, "inverse") and prop.inverse:
            try:
                if isinstance(prop.inverse, list):
                    property_inverse[prop.name] = prop.inverse[0].name
                else:
                    property_inverse[prop.name] = prop.inverse.name
            except (AttributeError, IndexError):
                # Just skip if we can't get the inverse property name
                pass
    
    # Analyze data properties
    for prop in data_properties:
        # Get characteristics
        characteristics = []
        if has_characteristic(prop, "Functional"):
            characteristics.append("Functional")
        
        property_characteristics[prop.name] = characteristics
        
        # Get domains and ranges
        domains = []
        ranges = []
        
        if hasattr(prop, "domain") and prop.domain:
            domains = [d.name if hasattr(d, "name") else str(d) for d in prop.domain]
        
        if hasattr(prop, "range") and prop.range:
            ranges = [r.name if hasattr(r, "name") else str(r) for r in prop.range]
        
        property_domains[prop.name] = domains
        property_ranges[prop.name] = ranges
    
    return {
        "object_properties": object_properties,
        "data_properties": data_properties,
        "annotation_properties": annotation_properties,
        "property_characteristics": property_characteristics,
        "property_domains": property_domains,
        "property_ranges": property_ranges,
        "property_inverse": property_inverse
    }

def analyze_individuals(onto):
    """Analyze individuals in the ontology."""
    individuals = list(onto.individuals())
    
    # Count individuals by class
    individual_classes = Counter()
    for ind in individuals:
        for cls in ind.is_a:
            if isinstance(cls, ThingClass):
                individual_classes[cls.name] += 1
    
    # Sample properties of individuals
    individual_properties = {}
    if individuals:
        sample_individual = individuals[0]
        props = []
        for prop in onto.object_properties():
            if hasattr(sample_individual, prop.name):
                props.append(prop.name)
        for prop in onto.data_properties():
            if hasattr(sample_individual, prop.name):
                props.append(prop.name)
        individual_properties[sample_individual.name] = props
    
    return {
        "individuals": individuals,
        "individual_count": len(individuals),
        "individual_classes": individual_classes,
        "individual_properties": individual_properties
    }

def analyze_restrictions(onto):
    """Analyze class restrictions in the ontology."""
    restrictions = {}
    
    for cls in onto.classes():
        class_restrictions = []
        
        for parent in cls.is_a:
            if not isinstance(parent, ThingClass):
                try:
                    if isinstance(parent, Restriction):
                        restriction_info = {
                            "type": "restriction",
                            "property": parent.property.name if hasattr(parent.property, "name") else str(parent.property),
                            "restriction_type": parent.__class__.__name__
                        }
                        
                        if hasattr(parent, "value"):
                            restriction_info["value"] = str(parent.value)
                        elif hasattr(parent, "cardinality"):
                            restriction_info["cardinality"] = parent.cardinality
                        
                        class_restrictions.append(restriction_info)
                    elif isinstance(parent, LogicalClassConstruct):
                        # Handle AND, OR, NOT constructs
                        restriction_info = {
                            "type": "logical",
                            "logical_type": parent.__class__.__name__,
                            "components": [c.name if hasattr(c, "name") else str(c) for c in parent.Classes]
                        }
                        class_restrictions.append(restriction_info)
                except Exception as e:
                    class_restrictions.append({"error": f"Error parsing restriction: {e}"})
        
        if class_restrictions:
            restrictions[cls.name] = class_restrictions
    
    return restrictions

def generate_sparql_query_templates(onto):
    """Generate sample SPARQL query templates for the ontology."""
    classes = list(onto.classes())
    object_properties = list(onto.object_properties())
    data_properties = list(onto.data_properties())
    
    templates = []
    
    # Only generate if we have classes
    if not classes:
        return templates
    
    # Basic class query
    sample_class = classes[0]
    basic_query = f"""
PREFIX onto: <{onto.base_iri}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?individual 
WHERE {{
    ?individual rdf:type onto:{sample_class.name} .
}}
LIMIT 10
"""
    templates.append(("List individuals of a class", basic_query))
    
    # Property-based query (if we have properties)
    if object_properties:
        sample_obj_prop = object_properties[0]
        domains = sample_obj_prop.domain
        ranges = sample_obj_prop.range
        
        if domains and ranges:
            domain_class = domains[0].name if hasattr(domains[0], "name") else "Thing"
            range_class = ranges[0].name if hasattr(ranges[0], "name") else "Thing"
            
            property_query = f"""
PREFIX onto: <{onto.base_iri}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?subject ?object
WHERE {{
    ?subject rdf:type onto:{domain_class} .
    ?object rdf:type onto:{range_class} .
    ?subject onto:{sample_obj_prop.name} ?object .
}}
LIMIT 10
"""
            templates.append(("Query by object property", property_query))
    
    # Data property query
    if data_properties:
        sample_data_prop = data_properties[0]
        domains = sample_data_prop.domain
        
        if domains:
            domain_class = domains[0].name if hasattr(domains[0], "name") else "Thing"
            
            data_property_query = f"""
PREFIX onto: <{onto.base_iri}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?individual ?value
WHERE {{
    ?individual rdf:type onto:{domain_class} .
    ?individual onto:{sample_data_prop.name} ?value .
}}
LIMIT 10
"""
            templates.append(("Query by data property", data_property_query))
    
    # Complex query with multiple classes and properties
    if len(classes) > 1 and len(object_properties) > 0:
        class1 = classes[0].name
        class2 = classes[1].name if len(classes) > 1 else classes[0].name
        obj_prop = object_properties[0].name
        
        complex_query = f"""
PREFIX onto: <{onto.base_iri}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?individual1 ?individual2
WHERE {{
    ?individual1 rdf:type onto:{class1} .
    ?individual2 rdf:type onto:{class2} .
    ?individual1 onto:{obj_prop} ?individual2 .
}}
LIMIT 10
"""
        templates.append(("Complex query", complex_query))
    
    return templates

def main():
    """Main function to analyze an OWL ontology."""
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python ontology_analyzer.py <path_to_owl_file>")
        print("Example: python ontology_analyzer.py test.owl")
        sys.exit(1)
    
    # Get file path
    file_path = sys.argv[1]
    
    # Check if file exists
    if not os.path.isfile(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)
    
    # Load ontology
    world, onto = load_ontology(file_path)
    
    print("\n" + "="*80)
    print(f"ONTOLOGY ANALYSIS: {file_path}")
    print("="*80)
    
    # Analyze namespaces
    print("\n--- NAMESPACES ---")
    namespaces = get_namespaces(world, onto)
    for prefix, namespace in namespaces.items():
        print(f"{prefix}: {namespace}")
    
    # Get ontology base IRI and preferred prefix
    print(f"\nBase IRI: {onto.base_iri}")
    
    # Analyze classes
    class_info = analyze_classes(onto)
    classes = class_info["classes"]
    
    print(f"\n--- CLASSES ({class_info['class_count']}) ---")
    if classes:
        # Sort classes by hierarchy depth
        sorted_classes = sorted(
            [(cls.name, class_info["class_depth"].get(cls, 0)) for cls in classes],
            key=lambda x: x[1]
        )
        
        # Print class hierarchy
        for cls_name, depth in sorted_classes:
            prefix = "  " * depth
            child_count = len(class_info["class_children"].get(cls_name, []))
            instance_count = class_info["instances_by_class"].get(cls_name, 0)
            print(f"{prefix}├─ {cls_name} ({instance_count} instances, {child_count} subclasses)")
    else:
        print("No classes found in the ontology.")
    
    # Analyze properties
    prop_info = analyze_properties(onto)
    
    print(f"\n--- OBJECT PROPERTIES ({len(prop_info['object_properties'])}) ---")
    if prop_info["object_properties"]:
        for prop in prop_info["object_properties"]:
            characteristics = ", ".join(prop_info["property_characteristics"].get(prop.name, []))
            domains = ", ".join(prop_info["property_domains"].get(prop.name, []))
            ranges = ", ".join(prop_info["property_ranges"].get(prop.name, []))
            inverse = prop_info["property_inverse"].get(prop.name, "")
            
            char_str = f" [{characteristics}]" if characteristics else ""
            inverse_str = f" (inverse: {inverse})" if inverse else ""
            
            print(f"├─ {prop.name}{char_str}{inverse_str}")
            print(f"│  ├─ Domain: {domains if domains else 'Thing'}")
            print(f"│  └─ Range: {ranges if ranges else 'Thing'}")
    else:
        print("No object properties found in the ontology.")
    
    print(f"\n--- DATA PROPERTIES ({len(prop_info['data_properties'])}) ---")
    if prop_info["data_properties"]:
        for prop in prop_info["data_properties"]:
            characteristics = ", ".join(prop_info["property_characteristics"].get(prop.name, []))
            domains = ", ".join(prop_info["property_domains"].get(prop.name, []))
            ranges = ", ".join(prop_info["property_ranges"].get(prop.name, []))
            
            char_str = f" [{characteristics}]" if characteristics else ""
            
            print(f"├─ {prop.name}{char_str}")
            print(f"│  ├─ Domain: {domains if domains else 'Thing'}")
            print(f"│  └─ Range: {ranges if ranges else 'rdfs:Literal'}")
    else:
        print("No data properties found in the ontology.")
    
    # Analyze individuals
    individual_info = analyze_individuals(onto)
    
    print(f"\n--- INDIVIDUALS ({individual_info['individual_count']}) ---")
    if individual_info["individuals"]:
        top_classes = individual_info["individual_classes"].most_common(5)
        print("Top 5 classes by individual count:")
        for cls_name, count in top_classes:
            print(f"├─ {cls_name}: {count} individuals")
        
        if individual_info["individual_properties"]:
            print("\nSample individual properties:")
            for ind_name, props in individual_info["individual_properties"].items():
                if props:
                    print(f"├─ {ind_name} has {len(props)} properties")
                    for i, prop in enumerate(props[:5]):
                        print(f"│  {'└─' if i == len(props[:5])-1 else '├─'} {prop}")
                    if len(props) > 5:
                        print(f"│  └─ ... and {len(props)-5} more")
    else:
        print("No individuals found in the ontology.")
    
    # Analyze restrictions
    restrictions = analyze_restrictions(onto)
    
    print(f"\n--- CLASS RESTRICTIONS ({len(restrictions)}) ---")
    if restrictions:
        for cls_name, class_restrictions in list(restrictions.items())[:5]:  # Show top 5
            print(f"├─ {cls_name}:")
            for i, restriction in enumerate(class_restrictions):
                if "error" in restriction:
                    print(f"│  {'└─' if i == len(class_restrictions)-1 else '├─'} Error: {restriction['error']}")
                elif restriction["type"] == "restriction":
                    rest_str = f"{restriction['property']} {restriction['restriction_type']}"
                    if "value" in restriction:
                        rest_str += f" {restriction['value']}"
                    elif "cardinality" in restriction:
                        rest_str += f" {restriction['cardinality']}"
                    print(f"│  {'└─' if i == len(class_restrictions)-1 else '├─'} {rest_str}")
                elif restriction["type"] == "logical":
                    print(f"│  {'└─' if i == len(class_restrictions)-1 else '├─'} {restriction['logical_type']} of {', '.join(restriction['components'])}")
        
        if len(restrictions) > 5:
            print(f"└─ ... and {len(restrictions)-5} more classes with restrictions")
    else:
        print("No class restrictions found in the ontology.")
    
    # Generate SPARQL query templates
    query_templates = generate_sparql_query_templates(onto)
    
    print(f"\n--- SPARQL QUERY TEMPLATES ({len(query_templates)}) ---")
    if query_templates:
        for i, (name, query) in enumerate(query_templates):
            print(f"\n{i+1}. {name}:")
            print(query)
    else:
        print("Could not generate SPARQL query templates.")
    
    print("\n" + "="*80)
    print("END OF ANALYSIS")
    print("="*80)

if __name__ == "__main__":
    main()