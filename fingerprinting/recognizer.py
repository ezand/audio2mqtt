"""Real-time audio stream recognizer using fingerprinting."""

import time
from collections import deque
from datetime import datetime
from typing import List, Dict, Optional

import numpy as np

from .engine import FingerprintEngine


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

        # Event debouncing
        self.last_event_time = {}

        # Statistics
        self.total_chunks = 0
        self.total_detections = 0
        self.skipped_silent_chunks = 0
        self.processed_chunks = 0

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
                'hashes_matched': match['hashes_matched_in_input']
            }
            detections.append(detection)

            if self.verbose:
                print(f"  → Match: {match['class']} @ {match['confidence']:.2f} "
                      f"(hashes: {match['hashes_matched_in_input']}/{match['input_total_hashes']})")

        elif self.verbose:
            # Log if audio was detected but no match found
            print(f"  → No match (threshold: {self.confidence_threshold})")

        # Filter debounced events
        filtered_detections = self._debounce_events(detections)
        self.total_detections += len(filtered_detections)

        return filtered_detections

    def _debounce_events(self, detections: List[Dict]) -> List[Dict]:
        """Filter out events that occurred too recently.

        Args:
            detections: List of detection dictionaries.

        Returns:
            Filtered list of detections.
        """
        current_time = time.time()
        filtered = []

        for detection in detections:
            event_class = detection['class']
            last_time = self.last_event_time.get(event_class, 0)

            if current_time - last_time >= self.debounce_duration:
                filtered.append(detection)
                self.last_event_time[event_class] = current_time

        return filtered

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
            'buffer_size': len(self.ring_buffer),
            'buffer_full': len(self.ring_buffer) >= self.window_size
        }

    def reset(self):
        """Reset recognizer state."""
        self.ring_buffer.clear()
        self.last_event_time.clear()
        self.total_chunks = 0
        self.total_detections = 0
        self.skipped_silent_chunks = 0
        self.processed_chunks = 0


def start_listening(device,
                   engine: FingerprintEngine,
                   chunk_duration: float = 0.5,
                   window_duration: float = 2.0,
                   confidence_threshold: float = 0.3,
                   energy_threshold_db: float = -40.0,
                   verbose: bool = False,
                   event_callback: Optional[callable] = None):
    """Start listening to audio device and recognize in real-time.

    Args:
        device: soundcard.Microphone object.
        engine: FingerprintEngine instance.
        chunk_duration: Duration of each audio chunk in seconds.
        window_duration: Duration of sliding window for recognition in seconds.
        confidence_threshold: Minimum confidence for event detection.
        energy_threshold_db: Minimum audio energy in dB to process.
        verbose: Enable verbose logging.
        event_callback: Optional callback function for detected events.
    """
    sample_rate = 16000
    chunk_size = int(chunk_duration * sample_rate)

    # Initialize recognizer
    stream_recognizer = StreamRecognizer(
        engine=engine,
        sample_rate=sample_rate,
        window_duration=window_duration,
        confidence_threshold=confidence_threshold,
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
                        print(f"[{timestamp}] Event detected: {detection['class']} "
                              f"(confidence: {detection['confidence']:.2f})")

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
        print("\nGoodbye!")
