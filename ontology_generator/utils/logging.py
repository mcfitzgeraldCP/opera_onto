"""
Logging utilities for the ontology generator.

This module provides functions for setting up and configuring logging.
"""
import logging
import sys
from typing import Optional, List

from ontology_generator.config import LOG_FORMAT

# --- Logger Instances ---
# Main module loggers that will be configured at initialization
logger = logging.getLogger("ontology_definition")  # Logger for definition module
pop_logger = logging.getLogger("ontology_population")  # Logger for population module
link_logger = logging.getLogger("event_linking")  # Logger for event linking pass
main_logger = logging.getLogger("create_ontology")  # Logger for main script
analysis_logger = logging.getLogger("ontology_analysis")  # Logger for analysis module

def configure_logging(
    log_level: int = logging.INFO,
    log_file: Optional[str] = None,
    handlers: Optional[List[logging.Handler]] = None
) -> None:
    """
    Configure the root logger with the specified settings.
    
    Args:
        log_level: The logging level to use (default: INFO)
        log_file: Optional path to a log file
        handlers: Optional list of handlers to add to the root logger
    """
    # Reset root logger configuration
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set up basic configuration
    logging.basicConfig(level=log_level, format=LOG_FORMAT, stream=sys.stdout)
    root_logger.setLevel(log_level)
    
    # Set all handler levels
    for handler in root_logger.handlers:
        handler.setLevel(log_level)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    
    # Add additional handlers if provided
    if handlers:
        for handler in handlers:
            root_logger.addHandler(handler)
    
    # Log confirmation
    main_logger.info("Logging configured.")
    if log_level == logging.DEBUG:
        main_logger.info("Verbose logging enabled (DEBUG level).")
    elif log_level == logging.WARNING:
        main_logger.info("Quiet logging enabled (WARNING level).")
    else:
        main_logger.info("Standard logging enabled (INFO level).")

def get_module_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module with the specified name.
    
    Args:
        name: The name of the logger
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)
