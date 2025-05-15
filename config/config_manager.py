"""
Configuration manager for loading and managing project settings.
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

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
    DEFAULT_RERANKER_MODEL,
    DEFAULT_USE_RERANKING,
    DEFAULT_DOCUMENT_PREFIXES,
    DEFAULT_USE_CLOUD_TRACKING,
    DEFAULT_CLOUD_TRACKING_PATH,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
)


class ConfigManager:
    """
    Manages configuration settings from environment variables and default values.
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration manager and load environment variables.
        
        Args:
            env_file: Path to .env file (default: None, will search in default locations)
        """
        # Load environment variables from .env file
        load_dotenv(dotenv_path=env_file)
        
        # Initialize configuration
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables and default constants.
        
        Returns:
            Dictionary of configuration values
        """
        config = {
            # Google Cloud settings
            "project_id": os.getenv("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID),
            "location": os.getenv("GOOGLE_CLOUD_LOCATION", DEFAULT_LOCATION),
            
            # RAG Engine settings
            "corpus_name": os.getenv("RAG_CORPUS_NAME", DEFAULT_CORPUS_NAME),
            "embedding_model": os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            "generative_model": os.getenv("RAG_GENERATIVE_MODEL", DEFAULT_GENERATIVE_MODEL),
            
            # Retrieval settings
            "top_k": int(os.getenv("RAG_TOP_K", DEFAULT_TOP_K)),
            "distance_threshold": float(os.getenv("RAG_DISTANCE_THRESHOLD", DEFAULT_DISTANCE_THRESHOLD)),
            "temperature": float(os.getenv("RAG_TEMPERATURE", DEFAULT_TEMPERATURE)),
            "reranker_model": os.getenv("RAG_RERANKER_MODEL", DEFAULT_RERANKER_MODEL),
            "use_reranking": os.getenv("RAG_USE_RERANKING", str(DEFAULT_USE_RERANKING)).lower() == "true",

            # GCS settings
            "gcs_bucket": os.getenv("GCS_BUCKET", DEFAULT_GCS_BUCKET),
            "document_prefixes": os.getenv("DOCUMENT_PREFIXES", ",".join(DEFAULT_DOCUMENT_PREFIXES)).split(","),
            "use_cloud_tracking": os.getenv("USE_CLOUD_TRACKING", str(DEFAULT_USE_CLOUD_TRACKING)).lower() == "true",
            "cloud_tracking_path": os.getenv("CLOUD_TRACKING_PATH", DEFAULT_CLOUD_TRACKING_PATH),
            
            # Document chunking settings
            "chunk_size": int(os.getenv("RAG_CHUNK_SIZE", DEFAULT_CHUNK_SIZE)),
            "chunk_overlap": int(os.getenv("RAG_CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP)),
        }
        
        # Validate required settings
        if not config["project_id"]:
            raise ValueError("Google Cloud Project ID not set. Please set GOOGLE_CLOUD_PROJECT environment variable.")
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self._config.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values.
        
        Returns:
            Dictionary of all configuration values
        """
        return self._config.copy()
    
    def update(self, key: str, value: Any) -> None:
        """
        Update configuration value.
        
        Args:
            key: Configuration key
            value: New value
        """
        self._config[key] = value


# Create singleton instance
config = ConfigManager()


def get_config() -> ConfigManager:
    """
    Get the configuration manager instance.
    
    Returns:
        ConfigManager instance
    """
    return config