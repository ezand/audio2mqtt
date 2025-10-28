"""Tests for storage_config module."""

import os
import pytest
from pathlib import Path

from fingerprinting.storage_config import (
    DatabaseType,
    get_database_config,
    get_memory_config,
    get_postgresql_config,
    get_mysql_config,
    load_config_from_file
)


def test_get_memory_config():
    """Test memory database configuration."""
    config = get_memory_config()

    assert config['database_type'] == 'memory'
    assert 'database' in config
    assert isinstance(config['database'], dict)


def test_get_postgresql_config_defaults():
    """Test PostgreSQL configuration with defaults."""
    config = get_postgresql_config()

    assert config['database_type'] == 'postgres'
    assert config['database']['host'] == 'localhost'
    assert config['database']['port'] == 5432
    assert config['database']['database'] == 'audio2mqtt'


def test_get_postgresql_config_with_params():
    """Test PostgreSQL configuration with custom parameters."""
    config = get_postgresql_config(
        host='custom_host',
        port=5433,
        database='custom_db',
        user='custom_user',
        password='custom_pass'
    )

    assert config['database']['host'] == 'custom_host'
    assert config['database']['port'] == 5433
    assert config['database']['database'] == 'custom_db'
    assert config['database']['user'] == 'custom_user'
    assert config['database']['password'] == 'custom_pass'


def test_get_postgresql_config_env_vars():
    """Test PostgreSQL configuration reads from environment variables."""
    # Set environment variables
    os.environ['POSTGRES_HOST'] = 'env_host'
    os.environ['POSTGRES_PORT'] = '5434'
    os.environ['POSTGRES_DB'] = 'env_db'
    os.environ['POSTGRES_USER'] = 'env_user'
    os.environ['POSTGRES_PASSWORD'] = 'env_pass'

    try:
        config = get_postgresql_config()

        assert config['database']['host'] == 'env_host'
        assert config['database']['port'] == 5434
        assert config['database']['database'] == 'env_db'
        assert config['database']['user'] == 'env_user'
        assert config['database']['password'] == 'env_pass'
    finally:
        # Clean up environment variables
        for key in ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']:
            os.environ.pop(key, None)


def test_get_mysql_config_defaults():
    """Test MySQL configuration with defaults."""
    config = get_mysql_config()

    assert config['database_type'] == 'mysql'
    assert config['database']['host'] == 'localhost'
    assert config['database']['port'] == 3306
    assert config['database']['database'] == 'audio2mqtt'


def test_get_database_config_memory():
    """Test get_database_config with MEMORY type."""
    config = get_database_config(db_type=DatabaseType.MEMORY)

    assert config['database_type'] == 'memory'


def test_get_database_config_postgresql():
    """Test get_database_config with POSTGRESQL type."""
    config = get_database_config(db_type=DatabaseType.POSTGRESQL)

    assert config['database_type'] == 'postgres'


def test_get_database_config_mysql():
    """Test get_database_config with MYSQL type."""
    config = get_database_config(db_type=DatabaseType.MYSQL)

    assert config['database_type'] == 'mysql'


def test_load_config_from_file(temp_dir):
    """Test loading configuration from YAML file."""
    config_path = temp_dir / "test_config.yaml"
    config_content = """fingerprint:
  database:
    type: postgresql
    host: test_host
    port: 5432
    database: test_db
    user: test_user
    password: test_pass
"""
    config_path.write_text(config_content)

    config = load_config_from_file(str(config_path))

    assert config['database_type'] == 'postgres'
    assert config['database']['host'] == 'test_host'
    assert config['database']['database'] == 'test_db'


def test_get_database_config_from_file(temp_dir):
    """Test get_database_config loads from file when provided."""
    config_path = temp_dir / "test_config.yaml"
    config_content = """fingerprint:
  database:
    type: memory
"""
    config_path.write_text(config_content)

    config = get_database_config(config_path=str(config_path))

    assert config['database_type'] == 'memory'


def test_load_config_nonexistent_file():
    """Test loading configuration from non-existent file returns None."""
    config = load_config_from_file('/path/to/nonexistent/file.yaml')

    assert config is None
