#!/usr/bin/env python3
"""
Test runner for ontology_generator tests.

This script runs tests for specific components of the ontology generator.
"""
import os
import sys
import logging
import importlib

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_runner")

def run_all_tests():
    """Run all tests and report results."""
    logger.info("=== Running all tests for ontology_generator ===")
    tests_to_run = [
        # Import path, test function name
        ("ontology_generator.utils.types", "_test_sanitize_name"),
        ("ontology_generator.tests.test_registry_sync", "test_registry_synchronization"),
    ]
    
    passed = 0
    failed = 0
    
    for module_path, function_name in tests_to_run:
        try:
            logger.info(f"Running {module_path}.{function_name}")
            module = importlib.import_module(module_path)
            test_func = getattr(module, function_name)
            result = test_func()
            
            # Handle different return formats
            if isinstance(result, tuple) and len(result) == 2:
                # Format used by _test_sanitize_name: (passed, failed)
                test_passed, test_failed = result
                if test_failed == 0:
                    logger.info(f"✓ {module_path}.{function_name} passed ({test_passed} subtests passed)")
                    passed += 1
                else:
                    logger.error(f"✗ {module_path}.{function_name} failed ({test_passed} passed, {test_failed} failed)")
                    failed += 1
            elif result is True:
                # Format used by test_registry_synchronization: single boolean
                logger.info(f"✓ {module_path}.{function_name} passed")
                passed += 1
            else:
                logger.error(f"✗ {module_path}.{function_name} failed or returned unexpected value")
                failed += 1
        except Exception as e:
            logger.error(f"Error running {module_path}.{function_name}: {e}", exc_info=True)
            failed += 1
    
    logger.info(f"=== Test run complete: {passed} passed, {failed} failed ===")
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 