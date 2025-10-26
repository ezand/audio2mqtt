"""In-memory database implementation for Dejavu (PyDejavu 0.1.3 compatible)."""

from dejavu.database import Database


class MemoryDatabase(Database):
    """Simple in-memory database for Dejavu fingerprinting.

    Compatible with PyDejavu 0.1.3 Database interface.
    Not persistent - data lost when process exits.
    """

    type = "memory"

    def __init__(self, **options):
        super(MemoryDatabase, self).__init__()
        self.songs = {}  # song_id -> {song_name, file_sha1, fingerprinted}
        self.fingerprints = []  # list of (hash, song_id, offset)
        self.next_song_id = 1

    def setup(self):
        """Initialize database (no-op for in-memory)."""
        pass

    def empty(self):
        """Clear all data."""
        self.songs = {}
        self.fingerprints = []
        self.next_song_id = 1

    def delete_unfingerprinted_songs(self):
        """Remove songs without fingerprints."""
        to_delete = [sid for sid, song in self.songs.items()
                     if not song.get('fingerprinted', False)]
        for sid in to_delete:
            del self.songs[sid]
            self.fingerprints = [(h, s, o) for h, s, o in self.fingerprints if s != sid]

    def get_num_songs(self):
        """Return number of fingerprinted songs."""
        return sum(1 for song in self.songs.values() if song.get('fingerprinted', False))

    def get_num_fingerprints(self):
        """Return total number of fingerprints."""
        return len(self.fingerprints)

    def get_song_fingerprint_count(self, song_id):
        """Return number of fingerprints for a specific song.

        Args:
            song_id: Song ID to query.

        Returns:
            Number of fingerprints for the song.
        """
        return sum(1 for h, s, o in self.fingerprints if s == song_id)

    def set_song_fingerprinted(self, sid):
        """Mark song as fingerprinted."""
        if sid in self.songs:
            self.songs[sid]['fingerprinted'] = True

    def get_songs(self):
        """Return all fingerprinted songs (yields dicts like DictCursor)."""
        for sid, song in self.songs.items():
            if song.get('fingerprinted', False):
                yield {
                    Database.FIELD_SONG_ID: sid,
                    Database.FIELD_SONGNAME: song['song_name'],
                    Database.FIELD_FILE_SHA1: song['file_sha1']
                }

    def get_song_by_id(self, sid):
        """Return song by ID as dict with string keys."""
        if sid in self.songs:
            song = self.songs[sid]
            return {
                'song_id': sid,
                'song_name': song['song_name'],
                'file_sha1': song['file_sha1']
            }
        return None

    def insert(self, hash, sid, offset):
        """Insert a single fingerprint."""
        self.fingerprints.append((hash, sid, offset))

    def insert_song(self, song_name, file_hash):
        """Insert a song and return its ID."""
        sid = self.next_song_id
        self.next_song_id += 1
        self.songs[sid] = {
            'song_name': song_name,
            'file_sha1': file_hash,
            'fingerprinted': False
        }
        return sid

    def query(self, hash):
        """Query fingerprints by hash."""
        if hash is None:
            # Return all fingerprints
            for h, sid, offset in self.fingerprints:
                yield (sid, offset)
        else:
            # Return matching fingerprints
            for h, sid, offset in self.fingerprints:
                if h == hash:
                    yield (sid, offset)

    def get_iterable_kv_pairs(self):
        """Return all fingerprints as list (for JSON serialization)."""
        return [(h, sid, offset) for h, sid, offset in self.fingerprints]

    def get_song_hashes(self, song_id):
        """Get all hashes for a specific song."""
        return [(h, offset) for h, sid, offset in self.fingerprints if sid == song_id]

    def insert_hashes(self, sid, hashes):
        """Insert multiple fingerprints."""
        for hash, offset in hashes:
            self.insert(hash, sid, offset)

    def return_matches(self, hashes):
        """Return matches for a list of hashes."""
        # Create hash -> offset mapping
        hash_dict = {h: offset for h, offset in hashes}

        # Find matches
        for hash, sid, db_offset in self.fingerprints:
            if hash in hash_dict:
                # Return (sid, offset_difference)
                yield (sid, db_offset - hash_dict[hash])
