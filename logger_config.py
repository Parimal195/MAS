# PRD Engine Logging Configuration
# Logs are written to logs/prd_engine.log

import os
import logging
import sys
from datetime import datetime
from pathlib import Path

# Create logs directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Configure logging
LOG_LEVEL = logging.DEBUG

def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """Setup a logger with both file and console handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Main PRD engine logger
prd_logger = setup_logger('PRDEngine', 'logs/prd_engine.log')

def log_api_check(logger, provider: str, available: bool, details: str = ""):
    """Log API availability check."""
    status = "✅ AVAILABLE" if available else "❌ NOT AVAILABLE"
    logger.info(f"API Check | {provider} | {status} | {details}")

def log_agent_start(logger, agent_name: str, task: str):
    """Log agent starting a task."""
    logger.info(f"AGENT START | {agent_name} | {task}")

def log_agent_end(logger, agent_name: str, status: str, details: str = ""):
    """Log agent completing a task."""
    logger.info(f"AGENT END   | {agent_name} | {status} | {details}")

def log_error(logger, component: str, error: str, context: str = ""):
    """Log an error with context."""
    logger.error(f"ERROR | {component} | {error} | Context: {context}")

def log_api_call(logger, provider: str, endpoint: str, status: str, details: str = ""):
    """Log API call details."""
    logger.debug(f"API CALL | {provider} | {endpoint} | {status} | {details}")

def log_section_generated(logger, section: str, word_count: int, option_count: int):
    """Log PRD section generation."""
    logger.info(f"SECTION GENERATED | {section} | {word_count} words | {option_count} options")