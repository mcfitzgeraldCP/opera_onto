"""
Population analysis module for the ontology generator.

This module provides functions for analyzing the ontology population.
"""
from typing import Dict, List, Set, Tuple, Any, Optional

from owlready2 import Ontology, Thing, ThingClass

from ontology_generator.utils.logging import analysis_logger

def analyze_ontology_population(onto: Ontology, 
                                defined_classes: Dict[str, ThingClass], 
                                specification: List[Dict[str, str]]
                               ) -> Tuple[Dict[str, int], List[str], Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Analyzes the population status of each class in the ontology.
    
    Args:
        onto: The ontology object
        defined_classes: Dictionary mapping class names to class objects
        specification: The original ontology specification
        
    Returns:
        tuple: (population_counts, empty_classes, class_instances, class_usage_info)
            - population_counts: Dict mapping class name to count of individuals
            - empty_classes: List of class names with no individuals
            - class_instances: Dict mapping class name to list of individual names
            - class_usage_info: Dict with additional usage analysis
    """
    analysis_logger.info("Starting analysis of ontology population")
    
    population_counts = {}
    empty_classes = []
    class_instances = {}
    
    # Extract the spec-defined classes
    spec_defined_classes = set()
    for row in specification:
        class_name = row.get('Proposed OWL Entity', '').strip()
        if class_name:
            spec_defined_classes.add(class_name)
    
    # Classes used in domain/range of properties
    property_domain_classes = set()
    property_range_classes = set()
    
    # Analyze property domains and ranges
    for prop in list(onto.object_properties()) + list(onto.data_properties()):
        if hasattr(prop, 'domain') and prop.domain:
            domains = prop.domain if isinstance(prop.domain, list) else [prop.domain]
            for domain in domains:
                if isinstance(domain, ThingClass):
                    property_domain_classes.add(domain.name)
        
        if hasattr(prop, 'range') and prop.range:
            ranges = prop.range if isinstance(prop.range, list) else [prop.range]
            for range_item in ranges:
                if isinstance(range_item, ThingClass):
                    property_range_classes.add(range_item.name)
    
    # Analyze instances
    for class_name, class_obj in defined_classes.items():
        # Skip owl:Thing which will have everything
        if class_obj is Thing:
            continue
            
        # Get all individuals of this class
        instances = list(onto.search(is_a=class_obj))
        count = len(instances)
        population_counts[class_name] = count
        
        if count == 0:
            empty_classes.append(class_name)
        else:
            # Store up to 10 instance names as examples
            sample_instances = [ind.name for ind in instances[:10]]
            class_instances[class_name] = sample_instances
    
    # Create class usage analysis
    class_usage_info = {
        'spec_defined': list(spec_defined_classes),
        'implemented_in_ontology': list(defined_classes.keys()),
        'in_property_domains': list(property_domain_classes),
        'in_property_ranges': list(property_range_classes),
        'populated_classes': list(set(defined_classes.keys()) - set(empty_classes)),
        'empty_classes': empty_classes,
        'extraneous_classes': list(set(defined_classes.keys()) - spec_defined_classes)
    }
    
    analysis_logger.info(f"Analysis complete. Found {len(population_counts)} classes, {len(empty_classes)} empty classes")
    return population_counts, empty_classes, class_instances, class_usage_info

def generate_population_report(population_counts: Dict[str, int], 
                               empty_classes: List[str], 
                               class_instances: Dict[str, List[str]],
                               defined_classes: Dict[str, ThingClass],
                               class_usage_info: Dict[str, List[str]] = None) -> str:
    """
    Generates a formatted report of the ontology population status.
    
    Args:
        population_counts: Dict mapping class name to count of individuals
        empty_classes: List of class names with no individuals
        class_instances: Dict mapping class name to list of individual names
        defined_classes: Dict mapping class names to class objects
        class_usage_info: Dict with additional usage analysis
        
    Returns:
        str: Formatted report text
    """
    report_lines = []
    
    # Add header
    report_lines.append("\n" + "="*80)
    report_lines.append(f"ONTOLOGY POPULATION REPORT")
    report_lines.append("="*80)
    
    # Summary statistics
    total_classes = len(defined_classes)
    populated_classes = total_classes - len(empty_classes)
    total_individuals = sum(population_counts.values())
    
    report_lines.append(f"\nSUMMARY:")
    report_lines.append(f"  • Total Classes: {total_classes}")
    report_lines.append(f"  • Populated Classes: {populated_classes} ({populated_classes/total_classes*100:.1f}%)")
    report_lines.append(f"  • Empty Classes: {len(empty_classes)} ({len(empty_classes)/total_classes*100:.1f}%)")
    report_lines.append(f"  • Total Individuals: {total_individuals}")
    
    # Spec vs. Implementation Analysis
    if class_usage_info:
        spec_defined = set(class_usage_info.get('spec_defined', []))
        implemented = set(class_usage_info.get('implemented_in_ontology', []))
        extraneous = set(class_usage_info.get('extraneous_classes', []))
        not_implemented = spec_defined - implemented
        
        report_lines.append("\nSPECIFICATION ANALYSIS:")
        report_lines.append(f"  • Classes in Specification: {len(spec_defined)}")
        report_lines.append(f"  • Classes Implemented in Ontology: {len(implemented)}")
        if extraneous:
            report_lines.append(f"  • Extraneous Classes (implemented but not in spec): {len(extraneous)}")
            report_lines.append(f"      {', '.join(sorted(list(extraneous)))}")
        if not_implemented:
            report_lines.append(f"  • Classes in Spec but Not Implemented: {len(not_implemented)}")
            report_lines.append(f"      {', '.join(sorted(list(not_implemented)))}")
        
        # Identify unused but defined classes
        used_in_properties = set(class_usage_info.get('in_property_domains', [])) | set(class_usage_info.get('in_property_ranges', []))
        populated = set(class_usage_info.get('populated_classes', []))
        unused_classes = implemented - used_in_properties - populated
        if unused_classes:
            report_lines.append(f"  • Completely Unused Classes (empty and not used in properties): {len(unused_classes)}")
            report_lines.append(f"      {', '.join(sorted(list(unused_classes)))}")
    
    # Populated classes
    report_lines.append("\nPOPULATED CLASSES (Class: Count)")
    populated_items = sorted([(k, v) for k, v in population_counts.items() if v > 0], 
                            key=lambda x: x[1], reverse=True)
    for class_name, count in populated_items:
        report_lines.append(f"  • {class_name}: {count}")
        # Add sample instances for classes with reasonable counts
        if count <= 20:  # Only show examples for classes with fewer instances
            examples = class_instances.get(class_name, [])
            if examples:
                report_lines.append(f"      Examples: {', '.join(examples[:5])}")
                if len(examples) > 5:
                    report_lines.append(f"      ... and {min(count, len(examples) - 5)} more")
    
    # Empty classes 
    if empty_classes:
        report_lines.append("\nEMPTY CLASSES:")
        for class_name in sorted(empty_classes):
            # Get parent class info for context
            class_obj = defined_classes.get(class_name)
            if class_obj and hasattr(class_obj, 'is_a') and class_obj.is_a:
                parent_names = [p.name for p in class_obj.is_a if p is not Thing]
                if parent_names:
                    # Check if used in property domain/range
                    usage = []
                    if class_usage_info and class_name in class_usage_info.get('in_property_domains', []):
                        usage.append("used in property domains")
                    if class_usage_info and class_name in class_usage_info.get('in_property_ranges', []):
                        usage.append("used in property ranges")
                    
                    if usage:
                        report_lines.append(f"  • {class_name} (subclass of: {', '.join(parent_names)}) - {', '.join(usage)}")
                    else:
                        report_lines.append(f"  • {class_name} (subclass of: {', '.join(parent_names)}) - COMPLETELY UNUSED")
                else:
                    report_lines.append(f"  • {class_name} (direct subclass of owl:Thing)")
            else:
                report_lines.append(f"  • {class_name}")
    
    # Add optimization recommendations
    report_lines.append("\nOPTIMIZATION RECOMMENDATIONS:")
    
    if class_usage_info and 'extraneous_classes' in class_usage_info and class_usage_info['extraneous_classes']:
        report_lines.append("  • Consider adding the extraneous classes to your specification for completeness")
    
    if class_usage_info and 'spec_defined' in class_usage_info and implemented - spec_defined:
        report_lines.append("  • Review and consider removing classes that are implemented but not in your spec")
    
    if unused_classes:
        report_lines.append("  • Consider removing completely unused classes that are neither populated nor referenced in properties")
    
    return "\n".join(report_lines)

def generate_optimization_recommendations(class_usage_info: Dict[str, List[str]],
                                      defined_classes: Dict[str, ThingClass]) -> Dict[str, List[str]]:
    """
    Generates specific recommendations for optimizing the ontology structure.
    
    Args:
        class_usage_info: Dict with usage analysis data
        defined_classes: Dictionary mapping class names to class objects
        
    Returns:
        Dict with categorized recommendations
    """
    recommendations = {
        'classes_to_remove': [],
        'extraneous_classes': [],
        'unused_properties': [],
        'configuration_options': []
    }
    
    # Extract necessary data from usage info
    implemented = set(class_usage_info.get('implemented_in_ontology', []))
    spec_defined = set(class_usage_info.get('spec_defined', []))
    extraneous = set(class_usage_info.get('extraneous_classes', []))
    empty_classes = set(class_usage_info.get('empty_classes', []))
    in_domains = set(class_usage_info.get('in_property_domains', []))
    in_ranges = set(class_usage_info.get('in_property_ranges', []))
    
    # Find used defined classes
    populated_classes = implemented - empty_classes
    used_in_properties = in_domains | in_ranges
    
    # Find completely unused classes (not populated and not in domains/ranges)
    completely_unused = implemented - populated_classes - used_in_properties
    
    # Classes that are extraneous AND empty
    unused_extraneous = extraneous & empty_classes & completely_unused
    
    # Generate recommendations
    if unused_extraneous:
        recommendations['classes_to_remove'].extend(list(unused_extraneous))
        recommendations['configuration_options'].append(
            "Add a 'CLASSES_TO_SKIP' list in your configuration to avoid creating these classes"
        )
    
    if extraneous:
        recommendations['extraneous_classes'].extend(list(extraneous))
        if len(extraneous) > 5:
            recommendations['configuration_options'].append(
                "Consider using a 'STRICT_SPEC_ADHERENCE' option to only create classes defined in the spec"
            )
    
    # Check parent-child relationships for optimization
    class_hierarchies = {}
    for class_name, class_obj in defined_classes.items():
        if hasattr(class_obj, 'is_a'):
            parents = [p.name for p in class_obj.is_a if p is not Thing]
            if parents:
                class_hierarchies[class_name] = parents
    
    # Find unused leaf classes (classes that are completely unused and have no children)
    leaf_classes = set()
    for class_name in completely_unused:
        has_children = False
        for _, parents in class_hierarchies.items():
            if class_name in parents:
                has_children = True
                break
        if not has_children:
            leaf_classes.add(class_name)
    
    if leaf_classes:
        recommendations['classes_to_remove'].extend(list(leaf_classes))
        recommendations['configuration_options'].append(
            "Consider adding a 'PRUNE_LEAF_CLASSES' option to automatically remove unused leaf classes"
        )
    
    # Remove duplicates and sort for consistency
    for key in recommendations:
        recommendations[key] = sorted(list(set(recommendations[key])))
    
    return recommendations
