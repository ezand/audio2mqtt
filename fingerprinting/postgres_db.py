"""PostgreSQL database adapter for Dejavu fingerprinting."""

from contextlib import contextmanager
from dejavu.database import Database

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    raise ImportError("psycopg2 required for PostgreSQL support. Install with: pip install psycopg2-binary")


class PostgreSQLDatabase(Database):
    """PostgreSQL database adapter for Dejavu.

    Compatible with PyDejavu 0.1.3 Database interface.
    Adapted from MySQL implementation in dejavu.database_sql.
    """

    type = "postgres"

    # Table names
    FINGERPRINTS_TABLENAME = "fingerprints"
    SONGS_TABLENAME = "songs"

    # Fields
    FIELD_FINGERPRINTED = "fingerprinted"

    # Create tables (PostgreSQL syntax with quoted identifiers)
    CREATE_SONGS_TABLE = f"""
        CREATE TABLE IF NOT EXISTS {SONGS_TABLENAME} (
            "{Database.FIELD_SONG_ID}" SERIAL PRIMARY KEY,
            "{Database.FIELD_SONGNAME}" VARCHAR(250) NOT NULL,
            "{FIELD_FINGERPRINTED}" SMALLINT DEFAULT 0,
            "{Database.FIELD_FILE_SHA1}" BYTEA NOT NULL,
            UNIQUE ("{Database.FIELD_SONG_ID}")
        );
    """

    CREATE_FINGERPRINTS_TABLE = f"""
        CREATE TABLE IF NOT EXISTS {FINGERPRINTS_TABLENAME} (
            "{Database.FIELD_HASH}" BYTEA NOT NULL,
            "{Database.FIELD_SONG_ID}" INTEGER NOT NULL,
            "{Database.FIELD_OFFSET}" INTEGER NOT NULL,
            FOREIGN KEY ("{Database.FIELD_SONG_ID}")
                REFERENCES {SONGS_TABLENAME}("{Database.FIELD_SONG_ID}") ON DELETE CASCADE,
            UNIQUE ("{Database.FIELD_SONG_ID}", "{Database.FIELD_OFFSET}", "{Database.FIELD_HASH}")
        );
    """

    CREATE_FINGERPRINTS_INDEX = f"""
        CREATE INDEX IF NOT EXISTS idx_fingerprints_hash
        ON {FINGERPRINTS_TABLENAME} ("{Database.FIELD_HASH}");
    """

    # Inserts (ON CONFLICT for deduplication)
    INSERT_FINGERPRINT = f"""
        INSERT INTO {FINGERPRINTS_TABLENAME} ("{Database.FIELD_HASH}", "{Database.FIELD_SONG_ID}", "{Database.FIELD_OFFSET}")
        VALUES (decode(%s, 'hex'), %s, %s)
        ON CONFLICT ("{Database.FIELD_SONG_ID}", "{Database.FIELD_OFFSET}", "{Database.FIELD_HASH}") DO NOTHING;
    """

    INSERT_SONG = f"""
        INSERT INTO {SONGS_TABLENAME} ("{Database.FIELD_SONGNAME}", "{Database.FIELD_FILE_SHA1}")
        VALUES (%s, decode(%s, 'hex'))
        RETURNING "{Database.FIELD_SONG_ID}";
    """

    # Selects
    SELECT = f"""
        SELECT "{Database.FIELD_SONG_ID}", "{Database.FIELD_OFFSET}"
        FROM {FINGERPRINTS_TABLENAME}
        WHERE "{Database.FIELD_HASH}" = decode(%s, 'hex');
    """

    SELECT_MULTIPLE = f"""
        SELECT encode("{Database.FIELD_HASH}", 'hex') as {Database.FIELD_HASH},
               "{Database.FIELD_SONG_ID}", "{Database.FIELD_OFFSET}"
        FROM {FINGERPRINTS_TABLENAME}
        WHERE "{Database.FIELD_HASH}" IN (%s);
    """

    SELECT_ALL = f"""
        SELECT "{Database.FIELD_SONG_ID}", "{Database.FIELD_OFFSET}"
        FROM {FINGERPRINTS_TABLENAME};
    """

    SELECT_SONG = f"""
        SELECT "{Database.FIELD_SONGNAME}",
               encode("{Database.FIELD_FILE_SHA1}", 'hex') as {Database.FIELD_FILE_SHA1}
        FROM {SONGS_TABLENAME}
        WHERE "{Database.FIELD_SONG_ID}" = %s;
    """

    SELECT_NUM_FINGERPRINTS = f"""
        SELECT COUNT(*) as n FROM {FINGERPRINTS_TABLENAME};
    """

    SELECT_UNIQUE_SONG_IDS = f"""
        SELECT COUNT(DISTINCT "{Database.FIELD_SONG_ID}") as n
        FROM {SONGS_TABLENAME}
        WHERE "{FIELD_FINGERPRINTED}" = 1;
    """

    SELECT_SONGS = f"""
        SELECT "{Database.FIELD_SONG_ID}", "{Database.FIELD_SONGNAME}",
               encode("{Database.FIELD_FILE_SHA1}", 'hex') as {Database.FIELD_FILE_SHA1}
        FROM {SONGS_TABLENAME}
        WHERE "{FIELD_FINGERPRINTED}" = 1;
    """

    # Drops
    DROP_FINGERPRINTS = f"DROP TABLE IF EXISTS {FINGERPRINTS_TABLENAME} CASCADE;"
    DROP_SONGS = f"DROP TABLE IF EXISTS {SONGS_TABLENAME} CASCADE;"

    # Update
    UPDATE_SONG_FINGERPRINTED = f"""
        UPDATE {SONGS_TABLENAME}
        SET "{FIELD_FINGERPRINTED}" = 1
        WHERE "{Database.FIELD_SONG_ID}" = %s;
    """

    # Delete
    DELETE_UNFINGERPRINTED = f"""
        DELETE FROM {SONGS_TABLENAME}
        WHERE "{FIELD_FINGERPRINTED}" = 0;
    """

    def __init__(self, **options):
        """Initialize PostgreSQL connection.

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
        """
        super(PostgreSQLDatabase, self).__init__()
        self.connection = psycopg2.connect(**options)
        self.connection.autocommit = False

    @contextmanager
    def cursor(self, cursor_type=DictCursor):
        """Context manager for database cursor."""
        cur = self.connection.cursor(cursor_factory=cursor_type)
        try:
            yield cur
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cur.close()

    def setup(self):
        """Create tables and indexes."""
        with self.cursor() as cur:
            cur.execute(self.CREATE_SONGS_TABLE)
            cur.execute(self.CREATE_FINGERPRINTS_TABLE)
            cur.execute(self.CREATE_FINGERPRINTS_INDEX)

    def empty(self):
        """Drop and recreate all tables."""
        with self.cursor() as cur:
            cur.execute(self.DROP_FINGERPRINTS)
            cur.execute(self.DROP_SONGS)
        self.setup()

    def delete_unfingerprinted_songs(self):
        """Delete songs that haven't been fingerprinted."""
        with self.cursor() as cur:
            cur.execute(self.DELETE_UNFINGERPRINTED)

    def get_num_songs(self):
        """Return number of fingerprinted songs."""
        with self.cursor() as cur:
            cur.execute(self.SELECT_UNIQUE_SONG_IDS)
            return cur.fetchone()['n']

    def get_num_fingerprints(self):
        """Return total number of fingerprints."""
        with self.cursor() as cur:
            cur.execute(self.SELECT_NUM_FINGERPRINTS)
            return cur.fetchone()['n']

    def set_song_fingerprinted(self, sid):
        """Mark song as fingerprinted."""
        with self.cursor() as cur:
            cur.execute(self.UPDATE_SONG_FINGERPRINTED, (sid,))

    def get_songs(self):
        """Return all fingerprinted songs as generator of dicts."""
        with self.cursor() as cur:
            cur.execute(self.SELECT_SONGS)
            for row in cur:
                yield row

    def get_song_by_id(self, sid):
        """Return song by ID as dict."""
        with self.cursor() as cur:
            cur.execute(self.SELECT_SONG, (sid,))
            return cur.fetchone()

    def insert(self, hash, sid, offset):
        """Insert a single fingerprint."""
        with self.cursor() as cur:
            cur.execute(self.INSERT_FINGERPRINT, (hash, sid, offset))

    def insert_song(self, song_name, file_hash):
        """Insert a song and return its ID."""
        with self.cursor() as cur:
            cur.execute(self.INSERT_SONG, (song_name, file_hash))
            return cur.fetchone()[0]

    def query(self, hash):
        """Query for hash matches (returns list of tuples)."""
        with self.cursor() as cur:
            cur.execute(self.SELECT, (hash,))
            return cur.fetchall()

    def get_iterable_kv_pairs(self):
        """Return all fingerprints as generator."""
        with self.cursor() as cur:
            cur.execute(self.SELECT_ALL)
            for row in cur:
                yield row

    def insert_hashes(self, sid, hashes):
        """Insert multiple fingerprints.

        Args:
            sid: Song ID
            hashes: Sequence of (hash, offset) tuples
        """
        values = [(h, sid, offset) for h, offset in hashes]
        with self.cursor() as cur:
            for hash_val, song_id, offset in values:
                cur.execute(self.INSERT_FINGERPRINT, (hash_val, song_id, offset))

    def return_matches(self, hashes):
        """Return matching fingerprints for given hashes.

        Args:
            hashes: Sequence of (hash, offset) tuples

        Returns:
            List of (song_id, offset_difference) tuples
        """
        if not hashes:
            return []

        # Prepare hash values for query
        hash_values = [h for h, _ in hashes]
        hash_dict = {h: offset for h, offset in hashes}

        # Debug: log first few hashes
        import os
        if os.environ.get('DEBUG_FINGERPRINT'):
            print(f"[DEBUG] Querying {len(hash_values)} hashes, first 3: {hash_values[:3]}")

        # Query database (manual expansion for IN clause)
        with self.cursor() as cur:
            # Build parameterized query for multiple hashes
            placeholders = ', '.join(['decode(%s, \'hex\')'] * len(hash_values))
            query = f"""
                SELECT "{Database.FIELD_HASH}", "{Database.FIELD_SONG_ID}", "{Database.FIELD_OFFSET}"
                FROM {self.FINGERPRINTS_TABLENAME}
                WHERE "{Database.FIELD_HASH}" IN ({placeholders});
            """
            cur.execute(query, hash_values)

            matches = []
            for row in cur:
                # Get hash, song_id, db_offset from result
                hash_hex = row[0].hex() if isinstance(row[0], bytes) else row[0]
                song_id = row[1]
                db_offset = row[2]

                # Calculate offset difference
                if hash_hex in hash_dict:
                    query_offset = hash_dict[hash_hex]
                    offset_diff = query_offset - db_offset
                    matches.append((song_id, offset_diff))

            if os.environ.get('DEBUG_FINGERPRINT'):
                print(f"[DEBUG] Found {len(matches)} matches")

            return matches

    def delete_unfingerprinted_song(self, sid):
        """Delete a specific song (fingerprinted or not)."""
        with self.cursor() as cur:
            cur.execute(f'DELETE FROM {self.SONGS_TABLENAME} WHERE "{Database.FIELD_SONG_ID}" = %s;', (sid,))

    def close(self):
        """Close database connection."""
        if hasattr(self, 'connection'):
            self.connection.close()
