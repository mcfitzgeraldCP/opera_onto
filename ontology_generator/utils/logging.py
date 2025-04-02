"""
Logging utilities for the ontology generator.

This module provides functions for setting up and configuring logging.
"""
import logging
import sys
from typing import Optional, List

from ontology_generator.config import LOG_FORMAT, SUPPRESSED_WARNINGS, MessageFilter, setup_logging_filters

# --- Logger Instances ---
# Main module loggers that will be configured at initialization
logger = logging.getLogger("ontology_definition")  # Logger for definition module
pop_logger = logging.getLogger("ontology_population")  # Logger for population module
link_logger = logging.getLogger("event_linking")  # Logger for event linking pass
main_logger = logging.getLogger("create_ontology")  # Logger for main script
analysis_logger = logging.getLogger("ontology_analysis")  # Logger for analysis module

class WarningSuppressionFilter(logging.Filter):
    """
    A logging filter that suppresses specific warning messages based on configured substrings.
    """
    def __init__(self, suppressed_warnings=None):
        super().__init__()
        self.suppressed_warnings = suppressed_warnings or []
        self.suppressed_count = 0
        
    def filter(self, record):
        if record.levelno == logging.WARNING:
            # Get the formatted message
            message = record.getMessage()
            # Check if any suppressed warning substring is in the message
            for suppressed in self.suppressed_warnings:
                if suppressed in message:
                    self.suppressed_count += 1
                    return False  # Suppress this warning
        return True  # Let other messages through

class InfoSuppressionFilter(logging.Filter):
    """
    A logging filter that suppresses specific INFO messages based on configured substrings.
    """
    def __init__(self, suppressed_info=None):
        super().__init__()
        self.suppressed_info = suppressed_info or []
        self.suppressed_count = 0
        
    def filter(self, record):
        if record.levelno == logging.INFO:
            # Get the formatted message
            message = record.getMessage()
            # Check if any suppressed info substring is in the message
            for suppressed in self.suppressed_info:
                if suppressed in message:
                    self.suppressed_count += 1
                    return False  # Suppress this info message
        return True  # Let other messages through

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
    
    # Set up warning suppression filter for specific loggers
    warning_filter = WarningSuppressionFilter(SUPPRESSED_WARNINGS)
    for logger_name in [
        "ontology_generator.population.row_processor",
        "ontology_population",
        "ontology_generator.population.equipment",
        "ontology_generator.population.events",
        "ontology_generator.population.core"
    ]:
        logging.getLogger(logger_name).addFilter(warning_filter)
    
    # Set up info suppression filter for individual creation messages
    info_filter = InfoSuppressionFilter(["Created new individual"])
    pop_logger.addFilter(info_filter)
    
    # Store filters for later access
    global _warning_filter, _info_filter
    _warning_filter = warning_filter
    _info_filter = info_filter
    
    # Set up message filter for SUPPRESSED_WARNINGS at all log levels
    setup_logging_filters()
    
    # Log confirmation
    main_logger.info("Logging configured.")
    if log_level == logging.DEBUG:
        main_logger.info("Verbose logging enabled (DEBUG level).")
    elif log_level == logging.WARNING:
        main_logger.info("Quiet logging enabled (WARNING level).")
    else:
        main_logger.info("Standard logging enabled (INFO level).")
    main_logger.info(f"Warning suppression filter applied for {len(SUPPRESSED_WARNINGS)} message patterns.")

# Global variables to store filter instances
_warning_filter = None
_info_filter = None

def get_suppressed_message_counts():
    """
    Get counts of suppressed messages.
    
    Returns:
        A tuple of (warning_count, info_count)
    """
    warning_count = _warning_filter.suppressed_count if _warning_filter else 0
    info_count = _info_filter.suppressed_count if _info_filter else 0
    return warning_count, info_count

def log_suppressed_message_counts():
    """
    Log the counts of suppressed messages.
    """
    warning_count, info_count = get_suppressed_message_counts()
    total_count = warning_count + info_count
    
    if total_count > 0:
        main_logger.info(f"Message suppression summary: {total_count} messages suppressed "
                         f"({warning_count} warnings, {info_count} info messages)")
    else:
        main_logger.info("No messages have been suppressed by filters")

def get_module_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module with the specified name.
    
    Args:
        name: The name of the logger
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)
