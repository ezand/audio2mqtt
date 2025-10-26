"""Fingerprint engine using Dejavu for audio recognition."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

import numpy as np

# Import database adapters BEFORE importing Dejavu to register them
from .memory_db import MemoryDatabase  # noqa: F401
from .postgres_db import PostgreSQLDatabase  # noqa: F401

from dejavu import Dejavu
from dejavu.recognize import FileRecognizer, MicrophoneRecognizer

from .storage_config import get_database_config, DatabaseType
from .metadata_db import MetadataDB


class FingerprintEngine:
    """Wrapper for Dejavu audio fingerprinting engine with metadata support."""

    def __init__(self,
                 db_type: DatabaseType = DatabaseType.MEMORY,
                 config_path: Optional[str] = None):
        """Initialize fingerprint engine.

        Args:
            db_type: Database type (MEMORY, POSTGRESQL, MYSQL).
            config_path: Path to config file (overrides db_type).
        """
        if config_path and os.path.exists(config_path):
            self.config = get_database_config(config_path=config_path)
        else:
            self.config = get_database_config(db_type=db_type)

        self.dejavu = Dejavu(self.config)
        self.metadata_db = MetadataDB(self.config)

    def register_file(self,
                     file_path: str,
                     song_name: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict:
        """Register a single audio file with optional metadata.

        Args:
            file_path: Path to audio file.
            song_name: Name to associate with fingerprint (defaults to filename).
            metadata: Optional metadata dictionary to store with fingerprint.

        Returns:
            Dictionary with registration info.
        """
        if song_name is None:
            song_name = Path(file_path).stem

        # Fingerprint the file
        self.dejavu.fingerprint_file(file_path, song_name=song_name)

        # Store metadata if provided
        if metadata:
            self.metadata_db.insert_metadata(
                song_name=song_name,
                metadata=metadata,
                source_file=file_path
            )

        return {
            'file': file_path,
            'song_name': song_name,
            'status': 'registered',
            'has_metadata': metadata is not None
        }

    def register_directory(self,
                          directory: str,
                          extensions: List[str] = ['.wav', '.mp3', '.m4a', '.ogg', '.flac'],
                          recursive: bool = True) -> List[Dict]:
        """Register all audio files in a directory.

        Args:
            directory: Path to directory.
            extensions: List of file extensions to include.
            recursive: Search subdirectories.

        Returns:
            List of registration results.
        """
        directory_path = Path(directory)
        results = []

        # Find all audio files
        pattern = '**/*' if recursive else '*'
        for ext in extensions:
            for file_path in directory_path.glob(f"{pattern}{ext}"):
                if file_path.is_file():
                    try:
                        result = self.register_file(str(file_path))
                        results.append(result)
                    except Exception as e:
                        results.append({
                            'file': str(file_path),
                            'song_name': None,
                            'status': 'error',
                            'error': str(e)
                        })

        return results

    def register_directory_by_class(self,
                                    training_dir: str,
                                    extensions: List[str] = ['.wav', '.mp3', '.m4a', '.ogg', '.flac']) -> Dict:
        """Register audio files organized by class folders.

        Expects structure: training_dir/class_name/*.wav

        Args:
            training_dir: Path to training directory.
            extensions: List of file extensions to include.

        Returns:
            Dictionary mapping class names to registration results.
        """
        training_path = Path(training_dir)
        results_by_class = {}

        # Iterate over class directories
        for class_dir in training_path.iterdir():
            if class_dir.is_dir():
                class_name = class_dir.name
                class_results = []

                # Register all files in class directory
                for ext in extensions:
                    for file_path in class_dir.glob(f"*{ext}"):
                        if file_path.is_file():
                            # Use class_name as song_name prefix
                            song_name = f"{class_name}_{file_path.stem}"
                            try:
                                result = self.register_file(str(file_path), song_name=song_name)
                                class_results.append(result)
                            except Exception as e:
                                class_results.append({
                                    'file': str(file_path),
                                    'song_name': song_name,
                                    'status': 'error',
                                    'error': str(e)
                                })

                results_by_class[class_name] = class_results

        return results_by_class

    def recognize_file(self, file_path: str, include_metadata: bool = True) -> Optional[Dict]:
        """Recognize audio from file.

        Args:
            file_path: Path to audio file.
            include_metadata: Whether to include metadata in result.

        Returns:
            Match result or None if no match.
        """
        results = self.dejavu.recognize(FileRecognizer, file_path)

        if results:
            # Extract class name from song_name (format: class_name_filename)
            song_name = results.get('song_name', '')
            class_name = song_name.split('_')[0] if '_' in song_name else song_name

            # Dejavu returns 'confidence' as number of matched hashes (not a 0-1 score)
            # We use this directly as our confidence metric
            matched_hashes = results.get('confidence', 0)

            result = {
                'class': class_name,
                'song_name': song_name,
                'confidence': matched_hashes,  # Use match count as confidence
                'offset': results.get('offset_seconds', 0),
                'input_total_hashes': matched_hashes,  # Dejavu doesn't provide this
                'fingerprinted_hashes_in_db': matched_hashes,
                'hashes_matched_in_input': matched_hashes
            }

            # Add metadata if requested
            if include_metadata:
                metadata_entry = self.metadata_db.get_metadata(song_name)
                if metadata_entry:
                    result['metadata'] = metadata_entry['metadata']

            return result

        return None

    def recognize_audio(self,
                       audio_data: np.ndarray,
                       sample_rate: int = 16000,
                       include_metadata: bool = True) -> Optional[Dict]:
        """Recognize audio from numpy array.

        Args:
            audio_data: Audio samples as numpy array.
            sample_rate: Sample rate in Hz.
            include_metadata: Whether to include metadata in result.

        Returns:
            Match result or None if no match.
        """
        # Dejavu expects mono audio as 1D array
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        # Convert to int16 if float
        if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
            audio_data = (audio_data * 32767).astype(np.int16)

        # Write to temporary WAV file (Dejavu limitation)
        import tempfile
        from scipy.io import wavfile

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            wavfile.write(tmp_path, sample_rate, audio_data)

        try:
            result = self.recognize_file(tmp_path, include_metadata=include_metadata)
        finally:
            os.unlink(tmp_path)

        return result

    def get_songs(self) -> List[Dict]:
        """Get list of registered songs.

        Returns:
            List of song dictionaries with id and name.
        """
        db = self.dejavu.db
        songs = db.get_songs()
        result = []
        for song in songs:
            # Handle both dict (MemoryDatabase) and tuple (SQL databases) formats
            if isinstance(song, dict):
                result.append({
                    'id': song.get(db.FIELD_SONG_ID) or song.get('song_id'),
                    'name': song.get(db.FIELD_SONGNAME) or song.get('song_name')
                })
            else:
                result.append({'id': song[0], 'name': song[1]})
        return result

    def get_song_count(self) -> int:
        """Get count of registered songs.

        Returns:
            Number of songs in database.
        """
        return len(self.get_songs())

    def delete_songs(self, song_names: List[str]) -> int:
        """Delete songs by name.

        Args:
            song_names: List of song names to delete.

        Returns:
            Number of songs deleted.
        """
        db = self.dejavu.db
        deleted_count = 0

        for song_name in song_names:
            # Get song info
            songs = db.get_songs()
            for song_id, name in songs:
                if name == song_name:
                    db.delete_unfingerprinted_song(song_id)
                    deleted_count += 1
                    break

        return deleted_count

    def clear_database(self) -> None:
        """Clear all fingerprints and metadata from database."""
        db = self.dejavu.db
        songs = db.get_songs()
        for song_id, _ in songs:
            db.delete_unfingerprinted_song(song_id)

        # Clear metadata as well
        self.metadata_db.clear_all_metadata()

    def get_metadata_for_song(self, song_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific song.

        Args:
            song_name: Song identifier.

        Returns:
            Metadata dictionary or None if not found.
        """
        return self.metadata_db.get_metadata(song_name)

    def query_songs_by_metadata(self, field: str, value: Any) -> List[Dict]:
        """Query songs by metadata field.

        Args:
            field: Metadata field name (supports dot notation for nested fields).
            value: Value to match.

        Returns:
            List of matching songs with metadata.
        """
        return self.metadata_db.query_by_field(field, value)

    def get_all_metadata(self) -> List[Dict]:
        """Get all song metadata.

        Returns:
            List of all metadata entries.
        """
        return self.metadata_db.get_all_metadata()

    def export_song_fingerprints(self, song_name: str) -> Optional[Dict]:
        """Export fingerprints and metadata for a song.

        Args:
            song_name: Song identifier.

        Returns:
            Dictionary with fingerprints and metadata or None if not found.
        """
        # Get song info
        db = self.dejavu.db
        songs = db.get_songs()
        song_id = None
        for sid, name in songs:
            if name == song_name:
                song_id = sid
                break

        if song_id is None:
            return None

        # Get fingerprints from database
        # Note: This requires direct database access which Dejavu doesn't expose nicely
        # For now, return structure without fingerprints (to be implemented if needed)
        metadata_entry = self.metadata_db.get_metadata(song_name)

        return {
            'song_name': song_name,
            'song_id': song_id,
            'metadata': metadata_entry['metadata'] if metadata_entry else {},
            'source_file': metadata_entry['source_file'] if metadata_entry else None,
            # 'fingerprints': []  # Would need custom Dejavu query
        }

    def close(self):
        """Close database connections."""
        if hasattr(self, 'metadata_db'):
            self.metadata_db.close()
