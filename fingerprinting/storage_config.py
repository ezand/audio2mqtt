"""Database storage configuration for Dejavu fingerprinting."""

import os
from enum import Enum
from typing import Dict, Optional

import yaml


class DatabaseType(Enum):
    """Supported database types."""
    MEMORY = "memory"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


def get_database_config(db_type: DatabaseType = DatabaseType.MEMORY,
                       config_path: Optional[str] = None) -> Dict:
    """Get database configuration for Dejavu.

    Args:
        db_type: Database type to use.
        config_path: Path to YAML config file (overrides db_type).

    Returns:
        Dejavu configuration dictionary.
    """
    if config_path and os.path.exists(config_path):
        return load_config_from_file(config_path)

    if db_type == DatabaseType.MEMORY:
        return get_memory_config()
    elif db_type == DatabaseType.POSTGRESQL:
        return get_postgresql_config()
    elif db_type == DatabaseType.MYSQL:
        return get_mysql_config()
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def get_memory_config() -> Dict:
    """Get in-memory database configuration.

    Note: Not persistent, data lost on restart.
    Good for development/testing.

    Returns:
        Dejavu configuration dictionary.
    """
    return {
        "database": {
            "type": "memory"
        }
    }


def get_postgresql_config(host: Optional[str] = None,
                          port: Optional[int] = None,
                          database: Optional[str] = None,
                          user: Optional[str] = None,
                          password: Optional[str] = None) -> Dict:
    """Get PostgreSQL database configuration.

    Args:
        host: Database host (default: from env or localhost).
        port: Database port (default: from env or 5432).
        database: Database name (default: from env or audio2mqtt).
        user: Database user (default: from env or audio2mqtt).
        password: Database password (default: from env).

    Returns:
        Dejavu configuration dictionary.
    """
    return {
        "database": {
            "type": "postgres",
            "host": host or os.getenv("POSTGRES_HOST", "localhost"),
            "port": port or int(os.getenv("POSTGRES_PORT", "5432")),
            "database": database or os.getenv("POSTGRES_DB", "audio2mqtt"),
            "user": user or os.getenv("POSTGRES_USER", "audio2mqtt"),
            "password": password or os.getenv("POSTGRES_PASSWORD", "")
        }
    }


def get_mysql_config(host: Optional[str] = None,
                    port: Optional[int] = None,
                    database: Optional[str] = None,
                    user: Optional[str] = None,
                    password: Optional[str] = None) -> Dict:
    """Get MySQL database configuration.

    Args:
        host: Database host (default: from env or localhost).
        port: Database port (default: from env or 3306).
        database: Database name (default: from env or audio2mqtt).
        user: Database user (default: from env or audio2mqtt).
        password: Database password (default: from env).

    Returns:
        Dejavu configuration dictionary.
    """
    return {
        "database": {
            "type": "mysql",
            "host": host or os.getenv("MYSQL_HOST", "localhost"),
            "port": port or int(os.getenv("MYSQL_PORT", "3306")),
            "database": database or os.getenv("MYSQL_DB", "audio2mqtt"),
            "user": user or os.getenv("MYSQL_USER", "audio2mqtt"),
            "password": password or os.getenv("MYSQL_PASSWORD", "")
        }
    }


def load_config_from_file(config_path: str) -> Dict:
    """Load database configuration from YAML file.

    Expected format:
        fingerprint:
          database:
            type: postgresql  # or mysql, memory
            host: localhost
            port: 5432
            database: audio2mqtt
            user: audio2mqtt
            password: secret

    Args:
        config_path: Path to YAML config file.

    Returns:
        Dejavu configuration dictionary.
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Extract fingerprint config
    fingerprint_config = config.get('fingerprint', {})
    db_config = fingerprint_config.get('database', {})

    db_type_str = db_config.get('type', 'memory').lower()

    if db_type_str == 'memory':
        return get_memory_config()
    elif db_type_str in ['postgresql', 'postgres']:
        return {
            "database": {
                "type": "postgres",
                "host": db_config.get('host', 'localhost'),
                "port": db_config.get('port', 5432),
                "database": db_config.get('database', 'audio2mqtt'),
                "user": db_config.get('user', 'audio2mqtt'),
                "password": db_config.get('password', '')
            }
        }
    elif db_type_str == 'mysql':
        return {
            "database": {
                "type": "mysql",
                "host": db_config.get('host', 'localhost'),
                "port": db_config.get('port', 3306),
                "database": db_config.get('database', 'audio2mqtt'),
                "user": db_config.get('user', 'audio2mqtt'),
                "password": db_config.get('password', '')
            }
        }
    else:
        raise ValueError(f"Unsupported database type in config: {db_type_str}")


def save_config_template(output_path: str, db_type: DatabaseType = DatabaseType.POSTGRESQL) -> None:
    """Save a template config file.

    Args:
        output_path: Path to save config template.
        db_type: Database type for template.
    """
    if db_type == DatabaseType.POSTGRESQL:
        template = {
            'fingerprint': {
                'database': {
                    'type': 'postgresql',
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'audio2mqtt',
                    'user': 'audio2mqtt',
                    'password': 'your_password_here'
                },
                'recognition': {
                    'chunk_seconds': 2.0,
                    'overlap': 0.5,
                    'confidence_threshold': 0.3
                }
            }
        }
    elif db_type == DatabaseType.MYSQL:
        template = {
            'fingerprint': {
                'database': {
                    'type': 'mysql',
                    'host': 'localhost',
                    'port': 3306,
                    'database': 'audio2mqtt',
                    'user': 'audio2mqtt',
                    'password': 'your_password_here'
                },
                'recognition': {
                    'chunk_seconds': 2.0,
                    'overlap': 0.5,
                    'confidence_threshold': 0.3
                }
            }
        }
    else:
        template = {
            'fingerprint': {
                'database': {
                    'type': 'memory'
                },
                'recognition': {
                    'chunk_seconds': 2.0,
                    'overlap': 0.5,
                    'confidence_threshold': 0.3
                }
            }
        }

    with open(output_path, 'w') as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)
