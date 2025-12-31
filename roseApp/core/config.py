"""
Unified configuration management system for Rose.

Provides a simple configuration system with:
1. System defaults
2. Configuration file (rose.config.yaml in current directory)
3. Environment variables (ROSE_*)
4. CLI arguments (highest priority)

Uses Pydantic for validation and type safety.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, validator
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field, validator
from enum import Enum


class CompressionType(str, Enum):
    """Available compression types"""
    NONE = "none"
    BZ2 = "bz2"
    LZ4 = "lz4"


class LogLevel(str, Enum):
    """Available log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RoseConfig(BaseSettings):
    """
    Unified Rose configuration with validation.
    
    Configuration hierarchy (highest to lowest priority):
    1. CLI arguments
    2. Environment variables (ROSE_*)
    3. Configuration file (rose.config.yaml)
    4. System defaults
    """
    
    # ===== Performance Settings =====
    parallel_workers: Optional[int] = Field(
        default=4,
        description="Number of parallel workers (auto-detect if None)"
    )
    
    memory_limit_mb: int = Field(
        default=512,
        description="Memory limit for operations in MB",
        ge=128,
        le=8192
    )
    
    # ===== Feature Toggles =====
    
    # ===== Default Behavior =====
    compression_default: CompressionType = Field(
        default=CompressionType.NONE,
        description="Default compression type"
    )
    
    verbose_default: bool = Field(
        default=False,
        description="Verbose output by default"
    )
    
    build_index_default: bool = Field(
        default=False,
        description="Build DataFrame index by default"
    )
    
    # ===== Logging Settings =====
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    
    log_to_file: bool = Field(
        default=True,
        description="Enable logging to file"
    )
    
    # ===== UI Settings =====
    theme_file: str = Field(
        default="rose.theme.default.yaml",
        description="Path to theme YAML file (name in config dir or absolute path)"
    )
    
    enable_colors: bool = Field(
        default=True,
        description="Enable colored output"
    )
    
    # ===== Directory Settings =====
    output_directory: str = Field(
        default="output",
        description="Default output directory for extracted bags"
    )
    
    cache_dir: Path = Field(
        default_factory=lambda: Path.home() / ".cache" / "rose",
        description="Directory for cache storage"
    )
    
    logs_dir: Path = Field(
        default_factory=lambda: Path("logs"),
        description="Directory for log files"
    )
    
    # ===== Validation =====
    
    @validator('cache_dir', 'logs_dir', pre=True)
    def ensure_path(cls, v):
        """Ensure all paths are Path objects"""
        if isinstance(v, str):
            return Path(v).expanduser()
        return v
    
    @validator('parallel_workers')
    def validate_workers(cls, v):
        """Validate parallel workers count"""
        if v is not None and v < 1:
            raise ValueError("parallel_workers must be at least 1")
        return v
    
    class Config:
        env_prefix = "ROSE_"
        env_file = ".env"
        case_sensitive = False
        
        # Allow extra fields for forward compatibility
        extra = "ignore"
    
    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist"""
        for dir_name in ['cache_dir', 'logs_dir']:
            dir_path = getattr(self, dir_name)
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def validate_config(self) -> Dict[str, Any]:
        """
        Validate current configuration and return validation results.
        
        Returns:
            Dict with validation status and any warnings/errors
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'info': []
        }
        
        # Check theme file exists
        theme_path = Path(self.theme_file)
        if not theme_path.exists():
            # Try roseApp/config
            app_config_theme = Path(__file__).parent.parent / "config" / self.theme_file
            if app_config_theme.exists():
                # Update to full path if found in config dir
                # But self.theme_file is immutable in validation? No, usually valid.
                pass 
            else:
                 # Try project root (legacy)
                 root_theme = Path(__file__).parent.parent.parent / self.theme_file
                 if not root_theme.exists():
                     results['warnings'].append(f"Theme file not found: {self.theme_file}")
        
        # Check directories are writable
        for dir_name in ['cache_dir', 'logs_dir']:
            dir_path = getattr(self, dir_name)
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                test_file = dir_path / '.write_test'
                test_file.touch()
                test_file.unlink()
            except Exception as e:
                results['errors'].append(f"{dir_name} not writable: {e}")
                results['valid'] = False
        
        # Check memory limit is reasonable
        if self.memory_limit_mb < 256:
            results['warnings'].append(f"Memory limit ({self.memory_limit_mb}MB) is low, may affect performance")
        
        # Check workers configuration
        if self.parallel_workers:
            cpu_count = os.cpu_count() or 4
            if self.parallel_workers > cpu_count:
                results['warnings'].append(f"Workers ({self.parallel_workers}) > CPU count ({cpu_count})")
        
        # Add info about loaded config
        loaded_path = getattr(self, '_loaded_config_path', None)
        if loaded_path:
            results['info'].append(f"Configuration loaded from: {loaded_path}")
        else:
            results['info'].append("Using default configuration")
        
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return self.dict()
    
    def save(self, path: Optional[Path] = None) -> None:
        """
        Save configuration to YAML file.
        
        Args:
            path: Path to save config (default: rose.config.yaml)
        """
        if path is None:
            path = Path("rose.config.yaml")
        
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict and save
        config_dict = {}
        for field_name, field in self.__fields__.items():
            value = getattr(self, field_name)
            
            # Convert Path objects to strings
            if isinstance(value, Path):
                value = str(value)
            # Convert Enum to value
            elif isinstance(value, Enum):
                value = value.value
            # Convert lists with Path objects
            elif isinstance(value, list):
                value = [str(v) if isinstance(v, Path) else v for v in value]
            
            config_dict[field_name] = value
        
        with open(path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'RoseConfig':
        """
        Load configuration from YAML file.
        
        Configuration search order (if path not specified):
        1. ./rose.config.yaml (current directory)
        2. ~/.rose/rose.config.yaml (user config)
        3. Default values
        
        Args:
            path: Path to config file (default: auto-search)
            
        Returns:
            RoseConfig instance with loaded_config_path attribute
        """
        config_data = {}
        loaded_config_path = None
        
        # Determine config file path
        if path is None:
            # Search in priority order
            search_paths = [
                Path("rose.config.yaml"),  # Current directory
                Path(__file__).parent.parent / "config" / "rose.config.yaml", # App config path
                Path.home() / ".rose" / "rose.config.yaml",  # User config
            ]
            
            for search_path in search_paths:
                if search_path.exists():
                    path = search_path
                    break
        
        # Try to load from file if found
        if path and path.exists():
            try:
                with open(path) as f:
                    config_data = yaml.safe_load(f) or {}
                loaded_config_path = path
            except Exception as e:
                # Log error but continue with defaults
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load config from {path}: {e}")
        
        # Load from environment and config file
        config = cls(**config_data)
        
        # Store the path that was actually loaded for logging
        config._loaded_config_path = loaded_config_path
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return getattr(self, key, default)


# Global configuration instance
_config: Optional[RoseConfig] = None


def get_config() -> RoseConfig:
    """
    Get global configuration instance.
    
    Creates configuration on first call by loading from:
    1. Environment variables (ROSE_*)
    2. Configuration file (rose.config.yaml in current directory)
    3. System defaults
    
    Returns:
        RoseConfig instance
    """
    global _config
    if _config is None:
        _config = RoseConfig.load()
        _config.ensure_directories()
        
        loaded_path = getattr(_config, '_loaded_config_path', None)
        
        # Validate configuration
        validation = _config.validate_config()
        
        # After config is loaded, reconfigure logging with the correct level
        from .logging import reconfigure_logging
        reconfigure_logging()
        
        # Now we can log with the correct level
        import logging
        logger = logging.getLogger(__name__)
        
        if loaded_path:
            logger.debug(f"Configuration loaded from: {loaded_path}")
        else:
            logger.debug("Using default configuration (no rose.config.yaml found)")
        
        if not validation['valid']:
            logger.error("Configuration validation failed")
            for error in validation['errors']:
                logger.error(f"  - {error}")
        
        if validation['warnings']:
            for warning in validation['warnings']:
                logger.warning(f"Config: {warning}")
            
    return _config


def set_config(config: RoseConfig) -> None:
    """
    Set global configuration instance.
    
    Args:
        config: Configuration to set
    """
    global _config
    _config = config


def reset_config() -> None:
    """Reset global configuration to defaults"""
    global _config
    _config = None


def update_config(**kwargs) -> RoseConfig:
    """
    Update global configuration with new values.
    
    Args:
        **kwargs: Configuration values to update
        
    Returns:
        Updated configuration
    """
    config = get_config()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config


# Convenience functions for common config access

def get_cache_dir() -> Path:
    """Get cache directory path"""
    return get_config().cache_dir


def get_logs_dir() -> Path:
    """Get logs directory path"""
    return get_config().logs_dir




def get_compression_default() -> str:
    """Get default compression type"""
    return get_config().compression_default.value


def get_theme_file() -> str:
    """Get current theme file"""
    return get_config().theme_file


def get_log_level() -> str:
    """Get current log level"""
    return get_config().log_level.value
