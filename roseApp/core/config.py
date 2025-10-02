"""
Unified configuration management system for Rose.

Provides a hierarchical configuration system with:
1. System defaults
2. User configuration file (~/.rose/config.yaml)
3. Project configuration file (.rose.yaml)
4. Environment variables (ROSE_*)
5. CLI arguments (highest priority)

Uses Pydantic for validation and type safety.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, validator
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field, validator
from enum import Enum


class ThemeMode(str, Enum):
    """Available theme modes"""
    CASSETTE_WALKMAN = "cassette-walkman"
    CASSETTE_DARK = "cassette-dark"
    CLAUDE_DARK = "claude-dark"
    CLAUDE_LIGHT = "claude-light"
    CLAUDE_MIDNIGHT = "claude-midnight"
    CLAUDE_HIGH_CONTRAST = "claude-high-contrast"


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
    3. Project config (.rose.yaml)
    4. User config (~/.rose/config.yaml)
    5. System defaults
    """
    
    # ===== Directory Settings =====
    cache_dir: Path = Field(
        default_factory=lambda: Path.home() / ".cache" / "rose",
        description="Directory for cache storage"
    )
    
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / ".rose",
        description="Directory for configuration files"
    )
    
    whitelists_dir: Path = Field(
        default_factory=lambda: Path.home() / ".rose" / "whitelists",
        description="Directory for whitelist files"
    )
    
    plugins_dir: Path = Field(
        default_factory=lambda: Path.home() / ".rose" / "plugins",
        description="Directory for user plugins"
    )
    
    logs_dir: Path = Field(
        default_factory=lambda: Path("logs"),
        description="Directory for log files"
    )
    
    temp_dir: Path = Field(
        default_factory=lambda: Path("logs") / "temp",
        description="Directory for temporary files"
    )
    
    # ===== UI Settings =====
    theme: ThemeMode = Field(
        default=ThemeMode.CASSETTE_WALKMAN,
        description="UI theme to use"
    )
    
    show_splash_screen: bool = Field(
        default=True,
        description="Show splash screen on startup"
    )
    
    use_rich_formatting: bool = Field(
        default=True,
        description="Use rich text formatting in CLI"
    )
    
    terminal_width: Optional[int] = Field(
        default=None,
        description="Terminal width (auto-detect if None)"
    )
    
    # ===== Performance Settings =====
    parallel_workers: Optional[int] = Field(
        default=None,
        description="Number of parallel workers (auto-detect if None)"
    )
    
    memory_limit_mb: int = Field(
        default=512,
        description="Memory limit for operations in MB",
        ge=128,
        le=8192
    )
    
    cache_size_limit_mb: int = Field(
        default=1024,
        description="Maximum cache size in MB",
        ge=100,
        le=10240
    )
    
    # ===== Feature Toggles =====
    enable_cache: bool = Field(
        default=True,
        description="Enable caching system"
    )
    
    enable_dataframes: bool = Field(
        default=True,
        description="Enable DataFrame generation"
    )
    
    enable_plugins: bool = Field(
        default=True,
        description="Enable plugin system"
    )
    
    enable_auto_load: bool = Field(
        default=True,
        description="Automatically load bags when needed"
    )
    
    # ===== Default Behavior =====
    compression_default: CompressionType = Field(
        default=CompressionType.LZ4,
        description="Default compression type"
    )
    
    build_index_default: bool = Field(
        default=False,
        description="Build DataFrame index by default"
    )
    
    overwrite_default: bool = Field(
        default=False,
        description="Overwrite existing files by default"
    )
    
    verbose_default: bool = Field(
        default=False,
        description="Verbose output by default"
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
    
    log_rotation: bool = Field(
        default=True,
        description="Enable log rotation"
    )
    
    log_max_size_mb: int = Field(
        default=10,
        description="Maximum log file size in MB before rotation"
    )
    
    log_backup_count: int = Field(
        default=5,
        description="Number of backup log files to keep"
    )
    
    # ===== Plugin Settings =====
    plugin_auto_discover: bool = Field(
        default=True,
        description="Automatically discover plugins on startup"
    )
    
    plugin_paths: List[str] = Field(
        default_factory=list,
        description="Additional plugin search paths"
    )
    
    disabled_plugins: List[str] = Field(
        default_factory=list,
        description="List of disabled plugin names"
    )
    
    # ===== Advanced Settings =====
    compress_cache: bool = Field(
        default=False,
        description="Compress cache files"
    )
    
    cache_eviction_policy: str = Field(
        default="lru",
        description="Cache eviction policy (lru, lfu, fifo)"
    )
    
    max_cache_age_hours: int = Field(
        default=168,  # 1 week
        description="Maximum age of cache entries in hours"
    )
    
    parser_type: str = Field(
        default="rosbags",
        description="Parser type to use (always 'rosbags')"
    )
    
    # ===== Validation =====
    
    @validator('cache_dir', 'config_dir', 'whitelists_dir', 'plugins_dir', 'logs_dir', 'temp_dir', pre=True)
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
    
    @validator('cache_eviction_policy')
    def validate_eviction_policy(cls, v):
        """Validate cache eviction policy"""
        if v not in ['lru', 'lfu', 'fifo']:
            raise ValueError(f"Invalid eviction policy: {v}")
        return v
    
    class Config:
        env_prefix = "ROSE_"
        env_file = ".env"
        case_sensitive = False
        
        # Allow extra fields for forward compatibility
        extra = "ignore"
    
    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist"""
        for dir_name in ['cache_dir', 'config_dir', 'whitelists_dir', 
                         'plugins_dir', 'logs_dir', 'temp_dir']:
            dir_path = getattr(self, dir_name)
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return self.dict()
    
    def save(self, path: Optional[Path] = None) -> None:
        """
        Save configuration to YAML file.
        
        Args:
            path: Path to save config (default: ~/.rose/config.yaml)
        """
        if path is None:
            path = self.config_dir / "config.yaml"
        
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
        
        Args:
            path: Path to config file (default: ~/.rose/config.yaml)
            
        Returns:
            RoseConfig instance
        """
        config_data = {}
        
        # Try to load from file
        if path is None:
            # Try user config
            user_config = Path.home() / ".rose" / "config.yaml"
            if user_config.exists():
                path = user_config
            else:
                # Try project config
                project_config = Path(".rose.yaml")
                if project_config.exists():
                    path = project_config
        
        if path and path.exists():
            with open(path) as f:
                config_data = yaml.safe_load(f) or {}
        
        # Load from environment and config file
        return cls(**config_data)
    
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
    2. User config file (~/.rose/config.yaml)
    3. Project config file (.rose.yaml)
    4. System defaults
    
    Returns:
        RoseConfig instance
    """
    global _config
    if _config is None:
        _config = RoseConfig.load()
        _config.ensure_directories()
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


def get_config_dir() -> Path:
    """Get config directory path"""
    return get_config().config_dir


def get_whitelists_dir() -> Path:
    """Get whitelists directory path"""
    return get_config().whitelists_dir


def get_plugins_dir() -> Path:
    """Get plugins directory path"""
    return get_config().plugins_dir


def get_logs_dir() -> Path:
    """Get logs directory path"""
    return get_config().logs_dir


def is_cache_enabled() -> bool:
    """Check if cache is enabled"""
    return get_config().enable_cache


def is_plugins_enabled() -> bool:
    """Check if plugins are enabled"""
    return get_config().enable_plugins


def get_compression_default() -> str:
    """Get default compression type"""
    return get_config().compression_default.value


def get_theme() -> str:
    """Get current theme"""
    return get_config().theme.value


def get_log_level() -> str:
    """Get current log level"""
    return get_config().log_level.value


# Migration helper for old code

def migrate_from_directories_module():
    """
    Helper function to migrate from old directories module.
    
    Old code using get_rose_directories() can be updated to use get_config()
    """
    from warnings import warn
    warn(
        "roseApp.core.directories is deprecated. Use roseApp.core.config instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_config()


