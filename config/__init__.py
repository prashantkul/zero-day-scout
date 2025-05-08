"""
Configuration module for the zero-day-scout project.
"""

from config.config_manager import get_config, ConfigManager
from config.constants import (
    DEFAULT_PROJECT_ID,
    DEFAULT_LOCATION,
    DEFAULT_CORPUS_NAME,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_GENERATIVE_MODEL,
    DEFAULT_TOP_K,
    DEFAULT_DISTANCE_THRESHOLD,
    DEFAULT_TEMPERATURE,
    DEFAULT_GCS_BUCKET,
)

__all__ = [
    "get_config",
    "ConfigManager",
    "DEFAULT_PROJECT_ID",
    "DEFAULT_LOCATION",
    "DEFAULT_CORPUS_NAME",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_GENERATIVE_MODEL",
    "DEFAULT_TOP_K",
    "DEFAULT_DISTANCE_THRESHOLD",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_GCS_BUCKET",
]