"""Real-time audio stream recognizer using fingerprinting."""

import time
from collections import deque
from datetime import datetime
from typing import List, Dict, Optional

import numpy as np

from .engine import FingerprintEngine
from .mqtt_client import MQTTPublisher


class StreamRecognizer:
    """Real-time audio stream recognizer using fingerprinting."""

    def __init__(self,
                 engine: FingerprintEngine,
                 sample_rate: int = 16000,
                 window_duration: float = 2.0,
                 hop_duration: float = 0.5,
                 confidence_threshold: float = 0.3,
                 debounce_duration: float = 1.0,
                 energy_threshold_db: float = -40.0,
                 verbose: bool = False):
        """Initialize stream recognizer.

        Args:
            engine: FingerprintEngine instance.
            sample_rate: Audio sample rate in Hz.
            window_duration: Duration of sliding window in seconds.
            hop_duration: Duration between windows in seconds.
            confidence_threshold: Minimum confidence for event detection.
            debounce_duration: Minimum time between same events in seconds.
            energy_threshold_db: Minimum audio energy in dB to process.
            verbose: Enable verbose logging.
        """
        self.engine = engine
        self.sample_rate = sample_rate
        self.confidence_threshold = confidence_threshold
        self.debounce_duration = debounce_duration
        self.energy_threshold_db = energy_threshold_db
        self.verbose = verbose

        # Calculate buffer sizes
        self.window_size = int(window_duration * sample_rate)
        self.hop_size = int(hop_duration * sample_rate)
        buffer_duration = window_duration + hop_duration
        self.buffer_size = int(buffer_duration * sample_rate)

        # Ring buffer for audio history
        self.ring_buffer = deque(maxlen=self.buffer_size)

        # Event debouncing for MQTT publishing
        self.last_event_time = {}
        self.last_published_song = None

        # Statistics
        self.total_chunks = 0
        self.total_detections = 0
        self.skipped_silent_chunks = 0
        self.processed_chunks = 0
        self.skipped_mqtt_publishes = 0

    def _calculate_energy_db(self, audio: np.ndarray) -> float:
        """Calculate audio energy in decibels.

        Args:
            audio: Audio samples (1D numpy array).

        Returns:
            Energy level in dB.
        """
        # Calculate RMS (root mean square) energy
        rms = np.sqrt(np.mean(audio**2))

        # Convert to dB (with safety check for silence)
        if rms > 1e-10:
            db = 20 * np.log10(rms)
        else:
            db = -100.0

        return db

    def process_chunk(self, audio_chunk: np.ndarray) -> List[Dict]:
        """Process an audio chunk and detect events.

        Args:
            audio_chunk: Audio samples (1D numpy array).

        Returns:
            List of detected events.
        """
        self.total_chunks += 1

        # Add chunk to ring buffer
        self.ring_buffer.extend(audio_chunk)

        # Check if buffer is full enough for inference
        if len(self.ring_buffer) < self.window_size:
            return []

        # Extract window from buffer
        window = np.array(list(self.ring_buffer)[-self.window_size:], dtype=np.float32)

        # Check audio energy - skip if too quiet
        energy_db = self._calculate_energy_db(window)
        if energy_db < self.energy_threshold_db:
            self.skipped_silent_chunks += 1
            return []

        # Audio detected - log if verbose
        self.processed_chunks += 1
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] Audio detected (energy: {energy_db:.1f} dB) - fingerprinting...")

        # Normalize to [-1.0, 1.0] if not already
        if window.max() > 1.0 or window.min() < -1.0:
            window = window / np.abs(window).max()

        # Recognize audio using fingerprinting
        match = self.engine.recognize_audio(window, self.sample_rate)

        # Convert match to detection format
        detections = []
        if match and match['confidence'] >= self.confidence_threshold:
            detection = {
                'class': match['class'],
                'confidence': match['confidence'],
                'song_name': match['song_name'],
                'offset': match['offset'],
                'hashes_matched_in_input': match.get('hashes_matched_in_input', 0),
                'input_total_hashes': match.get('input_total_hashes', 0),
                'hashes_matched': match.get('hashes_matched_in_input', 0),  # Alias for MQTT
                'metadata': match.get('metadata', {})  # Always include metadata field
            }

            detections.append(detection)

            if self.verbose:
                metadata_str = ""
                if 'metadata' in match:
                    meta = match['metadata']
                    if 'game' in meta and 'song' in meta:
                        metadata_str = f" [{meta['game']}: {meta['song']}]"
                    elif 'game' in meta:
                        metadata_str = f" [{meta['game']}]"
                    elif 'song' in meta:
                        metadata_str = f" [{meta['song']}]"
                print(f"  → Match: {match['class']}{metadata_str} @ {match['confidence']:.2f} "
                      f"(hashes: {match['hashes_matched_in_input']}/{match['input_total_hashes']})")

        elif self.verbose:
            # Log if audio was detected but no match found
            if match:
                print(f"  → No match (best: {match['class']} @ {match['confidence']:.2f}, "
                      f"hashes: {match['hashes_matched_in_input']}/{match['input_total_hashes']}, "
                      f"threshold: {self.confidence_threshold})")
            else:
                print(f"  → No match (no fingerprint matches found, threshold: {self.confidence_threshold})")

        # Return all detections (debouncing happens at MQTT publish level)
        self.total_detections += len(detections)
        return detections

    def _should_publish_to_mqtt(self, detection: Dict) -> tuple:
        """Check if detection should be published to MQTT based on debouncing rules.

        Rules:
        - If different song than last published → always publish (resets timer)
        - If same song → only publish if debounce_duration has passed
        - Uses per-song debounce_seconds from metadata if available, else global setting

        Args:
            detection: Detection dictionary with 'song_name' or 'class' field.

        Returns:
            Tuple of (should_publish: bool, skip_reason: Optional[str], time_since_last: Optional[float])
        """
        current_time = time.time()
        song_name = detection.get('song_name', detection.get('class'))

        # Get per-song debounce duration (should always be present in metadata)
        metadata = detection.get('metadata', {})
        debounce_duration = metadata.get('debounce_seconds', self.debounce_duration)

        # Validate (paranoid check)
        try:
            debounce_duration = max(0.0, float(debounce_duration))
        except (ValueError, TypeError):
            debounce_duration = self.debounce_duration

        # If this is a different song than the last published one, reset and publish
        if self.last_published_song != song_name:
            self.last_published_song = song_name
            self.last_event_time[song_name] = current_time
            return (True, None, None)

        # Same song - check debounce timing
        last_time = self.last_event_time.get(song_name, 0)
        time_since_last = current_time - last_time

        if time_since_last >= debounce_duration:
            # Debounce period passed - publish
            self.last_event_time[song_name] = current_time
            self.last_published_song = song_name
            return (True, None, time_since_last)
        else:
            # Within debounce window - skip (show actual duration used)
            return (False, f"within debounce window ({debounce_duration}s)", time_since_last)

    def get_stats(self) -> Dict:
        """Get recognizer statistics.

        Returns:
            Dictionary with statistics.
        """
        processed_chunks = self.total_chunks - self.skipped_silent_chunks
        return {
            'total_chunks': self.total_chunks,
            'processed_chunks': processed_chunks,
            'skipped_silent_chunks': self.skipped_silent_chunks,
            'total_detections': self.total_detections,
            'skipped_mqtt_publishes': self.skipped_mqtt_publishes,
            'buffer_size': len(self.ring_buffer),
            'buffer_full': len(self.ring_buffer) >= self.window_size
        }

    def reset(self):
        """Reset recognizer state."""
        self.ring_buffer.clear()
        self.last_event_time.clear()
        self.last_published_song = None
        self.total_chunks = 0
        self.total_detections = 0
        self.skipped_silent_chunks = 0
        self.processed_chunks = 0
        self.skipped_mqtt_publishes = 0


def start_listening(device,
                   engine: FingerprintEngine,
                   chunk_duration: float = 0.5,
                   window_duration: float = 2.0,
                   confidence_threshold: float = 0.3,
                   energy_threshold_db: float = -40.0,
                   debounce_duration: float = 5.0,
                   verbose: bool = False,
                   event_callback: Optional[callable] = None,
                   mqtt_publisher: Optional[MQTTPublisher] = None):
    """Start listening to audio device and recognize in real-time.

    Args:
        device: soundcard.Microphone object.
        engine: FingerprintEngine instance.
        chunk_duration: Duration of each audio chunk in seconds.
        window_duration: Duration of sliding window for recognition in seconds.
        confidence_threshold: Minimum confidence for event detection.
        energy_threshold_db: Minimum audio energy in dB to process.
        debounce_duration: Minimum time between MQTT publishes of same song in seconds.
        verbose: Enable verbose logging.
        event_callback: Optional callback function for detected events.
        mqtt_publisher: Optional MQTT publisher for event publishing.
    """
    # Use Dejavu's default sample rate (44.1kHz)
    from dejavu import fingerprint
    sample_rate = fingerprint.DEFAULT_FS
    chunk_size = int(chunk_duration * sample_rate)

    # Initialize recognizer
    stream_recognizer = StreamRecognizer(
        engine=engine,
        sample_rate=sample_rate,
        window_duration=window_duration,
        confidence_threshold=confidence_threshold,
        debounce_duration=debounce_duration,
        energy_threshold_db=energy_threshold_db,
        verbose=verbose
    )

    print(f"\nListening to: {device.name}")
    print(f"Method: Fingerprinting")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Chunk duration: {chunk_duration}s ({chunk_size} samples)")
    print(f"Window duration: {window_duration}s")
    print(f"Confidence threshold: {confidence_threshold}")
    print(f"Energy threshold: {energy_threshold_db} dB")
    if mqtt_publisher:
        print(f"MQTT debounce: {debounce_duration}s global (per-song override in metadata, resets on different song)")
    if verbose:
        print(f"Verbose mode: enabled")
    print("Press Ctrl+C to stop\n")

    try:
        with device.recorder(samplerate=sample_rate, channels=1) as recorder:
            while True:
                try:
                    # Record chunk
                    audio_chunk = recorder.record(numframes=chunk_size)

                    # Flatten to 1D if needed
                    if audio_chunk.ndim > 1:
                        audio_chunk = audio_chunk.mean(axis=1)

                    # Process chunk
                    detections = stream_recognizer.process_chunk(audio_chunk)

                    # Handle detections
                    for detection in detections:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Add timestamp to detection
                        detection['timestamp'] = timestamp

                        # Format output with metadata if available
                        metadata_str = ""
                        if 'metadata' in detection:
                            meta = detection['metadata']
                            parts = []
                            if 'game' in meta:
                                parts.append(f"game: {meta['game']}")
                            if 'song' in meta:
                                parts.append(f"song: {meta['song']}")
                            if parts:
                                metadata_str = f" ({', '.join(parts)})"

                        # Always print to console (no debouncing for console output)
                        print(f"[{timestamp}] Event detected: {detection['class']}{metadata_str} "
                              f"(confidence: {detection['confidence']:.2f})")

                        # Check if should publish to MQTT (with debouncing)
                        if mqtt_publisher:
                            should_publish, skip_reason, time_since_last = stream_recognizer._should_publish_to_mqtt(detection)

                            if should_publish:
                                mqtt_publisher.publish_event(detection)
                            else:
                                # Track skipped publishes
                                stream_recognizer.skipped_mqtt_publishes += 1

                                # Log skip if verbose mode enabled
                                if verbose:
                                    print(f"  → MQTT publish skipped: {skip_reason} (last: {time_since_last:.1f}s ago)")

                        # Call event callback if provided
                        if event_callback:
                            event_callback(detection)

                except KeyboardInterrupt:
                    # Break out of inner loop on Ctrl+C
                    break

    except KeyboardInterrupt:
        # Catch any KeyboardInterrupt that happens outside the recording loop
        pass
    finally:
        # Always print statistics
        print("\n\nStopping listener...")
        stats = stream_recognizer.get_stats()
        print(f"\nStatistics:")
        print(f"  Total chunks: {stats['total_chunks']}")
        print(f"  Processed chunks: {stats['processed_chunks']}")
        print(f"  Skipped (silent): {stats['skipped_silent_chunks']}")
        print(f"  Total detections: {stats['total_detections']}")
        if mqtt_publisher:
            print(f"  Skipped MQTT publishes: {stats['skipped_mqtt_publishes']}")
        print("\nGoodbye!")
