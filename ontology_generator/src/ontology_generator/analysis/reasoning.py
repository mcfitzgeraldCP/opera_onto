"""
Reasoning analysis module for the ontology generator.

This module provides functions for generating reasoning reports.
"""
from typing import Dict, List, Tuple, Any, Set

from owlready2 import Ontology, ThingClass

from ontology_generator.utils.logging import analysis_logger

def generate_reasoning_report(onto: Ontology,
                             pre_stats: Dict[str, int],
                             post_stats: Dict[str, int],
                             inconsistent_classes: List[ThingClass],
                             inferred_hierarchy: Dict[str, Dict[str, List[str]]],
                             inferred_properties: Dict[str, List[str]],
                             inferred_individuals: Dict[str, Dict[str, Any]],
                             use_reasoner: bool,
                             max_entities_per_category: int = 10,  # Parameter to limit entities shown
                             verbose: bool = False  # Parameter to control detail level
                            ) -> Tuple[str, bool]:
    """
    Generates a structured report from reasoning results.
    
    Args:
        onto: The ontology object
        pre_stats: Dict with pre-reasoning statistics
        post_stats: Dict with post-reasoning statistics
        inconsistent_classes: List of inconsistent classes
        inferred_hierarchy: Dict of inferred class relationships
        inferred_properties: Dict of inferred property characteristics
        inferred_individuals: Dict of inferred individual relationships
        use_reasoner: Whether the reasoner was used
        max_entities_per_category: Maximum number of entities to show per category
        verbose: Whether to show all details
    
    Returns:
        tuple: (report_str, has_issues)
    """
    report_lines = []
    has_issues = False

    def add_section(title):
        report_lines.extend(["\n" + "="*80, f"{title}", "="*80])

    # 1. Executive Summary
    add_section("REASONING REPORT EXECUTIVE SUMMARY")
    if inconsistent_classes:
        has_issues = True
        report_lines.append("❌ ONTOLOGY STATUS: Inconsistent")
        report_lines.append(f"    Found {len(inconsistent_classes)} inconsistent classes (see details below)")
    else:
        report_lines.append("✅ ONTOLOGY STATUS: Consistent")

    class_diff = post_stats['classes'] - pre_stats['classes']
    prop_diff = (post_stats['object_properties'] - pre_stats['object_properties'] +
                 post_stats['data_properties'] - pre_stats['data_properties'])
    ind_diff = post_stats['individuals'] - pre_stats['individuals']
    report_lines.extend([
        f"\nStructural Changes (Post-Reasoning vs Pre-Reasoning):",
        f"  • Classes: {class_diff:+d}", f"  • Properties (Obj + Data): {prop_diff:+d}", f"  • Individuals: {ind_diff:+d}"
    ])
    inferences_made = bool(inferred_hierarchy or inferred_properties or inferred_individuals)
    report_lines.append(f"\nInferences Made: {'Yes' if inferences_made else 'No'}")

    # 2. Detailed Statistics
    add_section("DETAILED STATISTICS")
    report_lines.extend([
        "\nPre-Reasoning:",
        f"  • Classes: {pre_stats['classes']}", f"  • Object Properties: {pre_stats['object_properties']}",
        f"  • Data Properties: {pre_stats['data_properties']}", f"  • Individuals: {pre_stats['individuals']}",
        "\nPost-Reasoning:",
        f"  • Classes: {post_stats['classes']}", f"  • Object Properties: {post_stats['object_properties']}",
        f"  • Data Properties: {post_stats['data_properties']}", f"  • Individuals: {post_stats['individuals']}"
    ])

    # 3. Consistency Issues
    if inconsistent_classes:
        add_section("CONSISTENCY ISSUES")
        report_lines.append("\nInconsistent Classes:")
        
        # Show all inconsistent classes regardless of verbosity - these are critical
        for cls in inconsistent_classes: 
            report_lines.append(f"  • {cls.name} ({cls.iri})")
        has_issues = True

    # 4. Inferred Knowledge
    add_section("INFERRED KNOWLEDGE")
    if inferred_hierarchy:
        report_lines.append("\nClass Hierarchy Changes:")
        
        # Apply entity limitation based on verbosity
        hierarchy_items = list(inferred_hierarchy.items())
        if not verbose and len(hierarchy_items) > max_entities_per_category:
            report_lines.append(f"  Showing {max_entities_per_category} of {len(hierarchy_items)} classes with hierarchy changes")
            hierarchy_items = hierarchy_items[:max_entities_per_category]
            
        for parent, data in hierarchy_items:
            if data.get('subclasses') or data.get('equivalent'):
                report_lines.append(f"\n  Class: {parent}")
                if data.get('subclasses'):
                    subclass_items = data['subclasses']
                    if not verbose and len(subclass_items) > max_entities_per_category:
                        report_lines.append(f"    ↳ Inferred Subclasses: ({len(subclass_items)} total, showing {max_entities_per_category})")
                        for sub in subclass_items[:max_entities_per_category]:
                            report_lines.append(f"        • {sub}")
                        report_lines.append(f"        • ... and {len(subclass_items) - max_entities_per_category} more")
                    else:
                        report_lines.append("    ↳ Inferred Subclasses:")
                        for sub in subclass_items:
                            report_lines.append(f"        • {sub}")
                
                if data.get('equivalent'):
                    equiv_items = data['equivalent']
                    if not verbose and len(equiv_items) > max_entities_per_category:
                        report_lines.append(f"    ≡ Inferred Equivalent Classes: {', '.join(equiv_items[:max_entities_per_category])} ... and {len(equiv_items) - max_entities_per_category} more")
                    else:
                        report_lines.append(f"    ≡ Inferred Equivalent Classes: {', '.join(equiv_items)}")
    else: 
        report_lines.append("\nNo new class hierarchy relationships inferred.")

    if inferred_properties:
        report_lines.append("\nInferred Property Characteristics:")
        
        # Apply entity limitation based on verbosity
        property_items = list(inferred_properties.items())
        if not verbose and len(property_items) > max_entities_per_category:
            report_lines.append(f"  Showing {max_entities_per_category} of {len(property_items)} properties with inferred characteristics")
            property_items = property_items[:max_entities_per_category]
            
        for prop, chars in property_items:
            report_lines.append(f"\n  Property: {prop}")
            if not verbose and len(chars) > max_entities_per_category:
                for char in chars[:max_entities_per_category]:
                    report_lines.append(f"    • {char}")
                report_lines.append(f"    • ... and {len(chars) - max_entities_per_category} more")
            else:
                for char in chars:
                    report_lines.append(f"    • {char}")
    else: 
        report_lines.append("\nNo new property characteristics inferred.")

    if inferred_individuals:
        report_lines.append("\nIndividual Inferences:")
        
        # Apply entity limitation based on verbosity
        individual_items = list(inferred_individuals.items())
        if not verbose and len(individual_items) > max_entities_per_category:
            report_lines.append(f"  Showing {max_entities_per_category} of {len(individual_items)} individuals with inferences")
            individual_items = individual_items[:max_entities_per_category]
            
        for ind_name, data in individual_items:
            report_lines.append(f"\n  Individual: {ind_name}")
            if data.get('types'):
                types_items = data['types']
                if not verbose and len(types_items) > max_entities_per_category:
                    report_lines.append(f"    Inferred Types: ({len(types_items)} total, showing {max_entities_per_category})")
                    for t in types_items[:max_entities_per_category]:
                        report_lines.append(f"      • {t}")
                    report_lines.append(f"      • ... and {len(types_items) - max_entities_per_category} more")
                else:
                    report_lines.append("    Inferred Types:")
                    for t in types_items:
                        report_lines.append(f"      • {t}")
                        
            if data.get('properties'):
                props_items = list(data['properties'].items())
                if not verbose and len(props_items) > max_entities_per_category:
                    report_lines.append(f"    Inferred Property Values: ({len(props_items)} total, showing {max_entities_per_category})")
                    for p, vals in props_items[:max_entities_per_category]:
                        if not verbose and len(vals) > max_entities_per_category:
                            report_lines.append(f"      • {p}: {', '.join(vals[:max_entities_per_category])} ... and {len(vals) - max_entities_per_category} more")
                        else:
                            report_lines.append(f"      • {p}: {', '.join(vals)}")
                    report_lines.append(f"      • ... and {len(props_items) - max_entities_per_category} more properties")
                else:
                    report_lines.append("    Inferred Property Values:")
                    for p, vals in props_items:
                        if not verbose and len(vals) > max_entities_per_category:
                            report_lines.append(f"      • {p}: {', '.join(vals[:max_entities_per_category])} ... and {len(vals) - max_entities_per_category} more")
                        else:
                            report_lines.append(f"      • {p}: {', '.join(vals)}")
    else: 
        report_lines.append("\nNo new individual types or property values inferred.")

    # 5. Recommendations
    add_section("RECOMMENDATIONS")
    recommendations = []
    if inconsistent_classes:
        recommendations.append("❗ HIGH PRIORITY: Resolve inconsistencies listed above.")
    if not inconsistent_classes and not inferences_made and use_reasoner:
        recommendations.append("⚠️ No inferences made - Ontology is consistent but may lack richness or reasoner configuration issue. Consider adding more specific axioms or reviewing reasoner setup.")
        # Don't flag as issue if reasoner wasn't run
        if use_reasoner: 
            has_issues = True
    if class_diff == 0 and prop_diff == 0 and ind_diff == 0 and use_reasoner:
       recommendations.append("ℹ️ No structural changes after reasoning - verify if this is expected.")
    if recommendations:
        report_lines.extend(["\n" + rec for rec in recommendations])
    else: 
        report_lines.append("\nNo critical issues or major inference gaps found.")

    return "\n".join(report_lines), has_issues
