"""Metadata database manager for song fingerprints."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    import MySQLdb
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

from .storage_config import DatabaseType


class MetadataDB:
    """Database manager for song metadata with JSONB support."""

    def __init__(self, db_config: Dict):
        """Initialize metadata database.

        Args:
            db_config: Database configuration dict from storage_config.
        """
        self.db_config = db_config
        # Get database_type from top level (Dejavu config format)
        self.db_type_str = db_config.get('database_type', 'memory')

        # Determine database type
        if self.db_type_str == 'postgres':
            self.db_type = DatabaseType.POSTGRESQL
        elif self.db_type_str == 'mysql':
            self.db_type = DatabaseType.MYSQL
        else:
            self.db_type = DatabaseType.MEMORY

        # Initialize connection
        self.conn = None
        self._init_connection()
        self._create_table()

    def _init_connection(self):
        """Initialize database connection."""
        if self.db_type == DatabaseType.POSTGRESQL:
            if not HAS_PSYCOPG2:
                raise ImportError("psycopg2 required for PostgreSQL support")

            db_info = self.db_config['database']
            self.conn = psycopg2.connect(
                host=db_info['host'],
                port=db_info['port'],
                database=db_info['database'],
                user=db_info['user'],
                password=db_info['password']
            )
            self.conn.autocommit = True

        elif self.db_type == DatabaseType.MYSQL:
            if not HAS_MYSQL:
                raise ImportError("MySQLdb required for MySQL support")

            db_info = self.db_config['database']
            self.conn = MySQLdb.connect(
                host=db_info['host'],
                port=db_info['port'],
                db=db_info['database'],
                user=db_info['user'],
                passwd=db_info['password']
            )
            self.conn.autocommit(True)

        else:  # Memory/SQLite
            # Use in-memory SQLite database
            self.conn = sqlite3.connect(':memory:')
            self.conn.row_factory = sqlite3.Row

    def _create_table(self):
        """Create metadata table if it doesn't exist."""
        if self.db_type == DatabaseType.POSTGRESQL:
            create_sql = """
                CREATE TABLE IF NOT EXISTS song_metadata (
                    song_name VARCHAR(250) PRIMARY KEY,
                    metadata JSONB NOT NULL,
                    source_file VARCHAR(500),
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_song_metadata_jsonb
                    ON song_metadata USING GIN (metadata);
            """
        elif self.db_type == DatabaseType.MYSQL:
            create_sql = """
                CREATE TABLE IF NOT EXISTS song_metadata (
                    song_name VARCHAR(250) PRIMARY KEY,
                    metadata JSON NOT NULL,
                    source_file VARCHAR(500),
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
        else:  # SQLite
            create_sql = """
                CREATE TABLE IF NOT EXISTS song_metadata (
                    song_name VARCHAR(250) PRIMARY KEY,
                    metadata TEXT NOT NULL,
                    source_file VARCHAR(500),
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """

        cursor = self.conn.cursor()
        if self.db_type == DatabaseType.POSTGRESQL:
            # Execute multiple statements for PostgreSQL
            for statement in create_sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
        else:
            cursor.execute(create_sql)
        cursor.close()

    def insert_metadata(self,
                       song_name: str,
                       metadata: Dict[str, Any],
                       source_file: Optional[str] = None) -> None:
        """Insert or update metadata for a song.

        Args:
            song_name: Unique song identifier.
            metadata: Dictionary of metadata fields.
            source_file: Original source file path.
        """
        cursor = self.conn.cursor()

        # Serialize metadata based on database type
        if self.db_type in [DatabaseType.POSTGRESQL, DatabaseType.MYSQL]:
            # PostgreSQL and MySQL handle JSON natively
            metadata_value = json.dumps(metadata)
        else:
            # SQLite stores as TEXT
            metadata_value = json.dumps(metadata)

        if self.db_type == DatabaseType.POSTGRESQL:
            sql = """
                INSERT INTO song_metadata (song_name, metadata, source_file, date_added)
                VALUES (%s, %s::jsonb, %s, %s)
                ON CONFLICT (song_name)
                DO UPDATE SET metadata = EXCLUDED.metadata,
                             source_file = EXCLUDED.source_file,
                             date_added = EXCLUDED.date_added;
            """
            cursor.execute(sql, (song_name, metadata_value, source_file, datetime.now()))

        elif self.db_type == DatabaseType.MYSQL:
            sql = """
                INSERT INTO song_metadata (song_name, metadata, source_file, date_added)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    metadata = VALUES(metadata),
                    source_file = VALUES(source_file),
                    date_added = VALUES(date_added);
            """
            cursor.execute(sql, (song_name, metadata_value, source_file, datetime.now()))

        else:  # SQLite
            sql = """
                INSERT OR REPLACE INTO song_metadata
                (song_name, metadata, source_file, date_added)
                VALUES (?, ?, ?, ?);
            """
            cursor.execute(sql, (song_name, metadata_value, source_file, datetime.now()))
            self.conn.commit()

        cursor.close()

    def get_metadata(self, song_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a song.

        Args:
            song_name: Song identifier.

        Returns:
            Metadata dictionary or None if not found.
        """
        cursor = self.conn.cursor()

        if self.db_type == DatabaseType.POSTGRESQL:
            cursor.execute(
                "SELECT metadata, source_file FROM song_metadata WHERE song_name = %s",
                (song_name,)
            )
        elif self.db_type == DatabaseType.MYSQL:
            cursor.execute(
                "SELECT metadata, source_file FROM song_metadata WHERE song_name = %s",
                (song_name,)
            )
        else:  # SQLite
            cursor.execute(
                "SELECT metadata, source_file FROM song_metadata WHERE song_name = ?",
                (song_name,)
            )

        row = cursor.fetchone()
        cursor.close()

        if row:
            if self.db_type in [DatabaseType.POSTGRESQL, DatabaseType.MYSQL]:
                metadata = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            else:  # SQLite
                metadata = json.loads(row[0])

            return {
                'metadata': metadata,
                'source_file': row[1]
            }

        return None

    def query_by_field(self, field_path: str, value: Any) -> List[Dict[str, Any]]:
        """Query songs by metadata field.

        Args:
            field_path: Dot-notation path to field (e.g., 'game', 'artist.name').
            value: Value to match.

        Returns:
            List of matching songs with metadata.
        """
        cursor = self.conn.cursor()
        results = []

        if self.db_type == DatabaseType.POSTGRESQL:
            # PostgreSQL JSONB query
            if '.' in field_path:
                # Nested field: metadata->'artist'->>'name'
                parts = field_path.split('.')
                json_path = "->".join(f"'{p}'" for p in parts[:-1])
                last_key = parts[-1]
                sql = f"""
                    SELECT song_name, metadata, source_file
                    FROM song_metadata
                    WHERE metadata->{json_path}->>{last_key} = %s
                """
            else:
                # Top-level field: metadata->>'game'
                sql = f"""
                    SELECT song_name, metadata, source_file
                    FROM song_metadata
                    WHERE metadata->>%s = %s
                """
                cursor.execute(sql, (field_path, str(value)))

            if '.' not in field_path:
                cursor.execute(sql, (field_path, str(value)))
            else:
                cursor.execute(sql, (str(value),))

            rows = cursor.fetchall()
            for row in rows:
                results.append({
                    'song_name': row[0],
                    'metadata': row[1] if isinstance(row[1], dict) else json.loads(row[1]),
                    'source_file': row[2]
                })

        elif self.db_type == DatabaseType.MYSQL:
            # MySQL JSON query (less efficient than PostgreSQL)
            sql = """
                SELECT song_name, metadata, source_file
                FROM song_metadata
                WHERE JSON_EXTRACT(metadata, %s) = %s
            """
            json_path = f'$.{field_path}'
            cursor.execute(sql, (json_path, json.dumps(value)))

            rows = cursor.fetchall()
            for row in rows:
                results.append({
                    'song_name': row[0],
                    'metadata': json.loads(row[1]) if isinstance(row[1], str) else row[1],
                    'source_file': row[2]
                })

        else:  # SQLite - requires full scan
            cursor.execute("SELECT song_name, metadata, source_file FROM song_metadata")
            rows = cursor.fetchall()
            for row in rows:
                metadata = json.loads(row[1])
                # Navigate field path
                field_value = metadata
                for part in field_path.split('.'):
                    if isinstance(field_value, dict) and part in field_value:
                        field_value = field_value[part]
                    else:
                        field_value = None
                        break

                if field_value == value:
                    results.append({
                        'song_name': row[0],
                        'metadata': metadata,
                        'source_file': row[2]
                    })

        cursor.close()
        return results

    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """Get all song metadata.

        Returns:
            List of all metadata entries.
        """
        cursor = self.conn.cursor()

        if self.db_type in [DatabaseType.POSTGRESQL, DatabaseType.MYSQL]:
            cursor.execute("SELECT song_name, metadata, source_file FROM song_metadata")
        else:
            cursor.execute("SELECT song_name, metadata, source_file FROM song_metadata")

        rows = cursor.fetchall()
        cursor.close()

        results = []
        for row in rows:
            if self.db_type in [DatabaseType.POSTGRESQL, DatabaseType.MYSQL]:
                metadata = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            else:
                metadata = json.loads(row[1])

            results.append({
                'song_name': row[0],
                'metadata': metadata,
                'source_file': row[2]
            })

        return results

    def delete_metadata(self, song_name: str) -> bool:
        """Delete metadata for a song.

        Args:
            song_name: Song identifier.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self.conn.cursor()

        if self.db_type == DatabaseType.POSTGRESQL:
            cursor.execute("DELETE FROM song_metadata WHERE song_name = %s", (song_name,))
        elif self.db_type == DatabaseType.MYSQL:
            cursor.execute("DELETE FROM song_metadata WHERE song_name = %s", (song_name,))
        else:
            cursor.execute("DELETE FROM song_metadata WHERE song_name = ?", (song_name,))
            self.conn.commit()

        deleted = cursor.rowcount > 0
        cursor.close()
        return deleted

    def clear_all_metadata(self) -> None:
        """Clear all metadata from database."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM song_metadata")
        if self.db_type == DatabaseType.MEMORY:
            self.conn.commit()
        cursor.close()

    def count_metadata(self) -> int:
        """Get count of metadata entries.

        Returns:
            Number of metadata entries.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM song_metadata")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
