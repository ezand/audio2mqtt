"""Real-time audio stream classification."""

import time
from collections import deque
from datetime import datetime
from typing import List, Dict, Optional, Callable

import numpy as np
import tensorflow as tf

from model import extract_embeddings, predict_streaming


class StreamClassifier:
    """Real-time audio stream classifier using YAMNet + custom model."""

    def __init__(self,
                 yamnet_model,
                 classifier: tf.keras.Model,
                 class_names: List[str],
                 sample_rate: int = 16000,
                 window_duration: float = 2.0,
                 hop_duration: float = 0.5,
                 confidence_threshold: float = 0.7,
                 debounce_duration: float = 1.0):
        """Initialize stream classifier.

        Args:
            yamnet_model: Loaded YAMNet model.
            classifier: Trained classifier model.
            class_names: List of class names.
            sample_rate: Audio sample rate in Hz.
            window_duration: Duration of sliding window in seconds.
            hop_duration: Duration between windows in seconds.
            confidence_threshold: Minimum confidence for event detection.
            debounce_duration: Minimum time between same events in seconds.
        """
        self.yamnet_model = yamnet_model
        self.classifier = classifier
        self.class_names = class_names
        self.sample_rate = sample_rate
        self.confidence_threshold = confidence_threshold
        self.debounce_duration = debounce_duration

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

        # Normalize to [-1.0, 1.0] if not already
        if window.max() > 1.0 or window.min() < -1.0:
            window = window / np.abs(window).max()

        # Convert to tensor
        waveform = tf.constant(window, dtype=tf.float32)

        # Extract embeddings
        embeddings = extract_embeddings(self.yamnet_model, waveform)

        # Get detections
        detections = predict_streaming(
            self.classifier,
            embeddings,
            self.class_names,
            threshold=self.confidence_threshold
        )

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
        """Get classifier statistics.

        Returns:
            Dictionary with statistics.
        """
        return {
            'total_chunks': self.total_chunks,
            'total_detections': self.total_detections,
            'buffer_size': len(self.ring_buffer),
            'buffer_full': len(self.ring_buffer) >= self.window_size
        }

    def reset(self):
        """Reset classifier state."""
        self.ring_buffer.clear()
        self.last_event_time.clear()
        self.total_chunks = 0
        self.total_detections = 0


def start_listening(device,
                   yamnet_model,
                   classifier: tf.keras.Model,
                   class_names: List[str],
                   chunk_duration: float = 0.5,
                   confidence_threshold: float = 0.7,
                   event_callback: Optional[Callable[[Dict], None]] = None):
    """Start listening to audio device and classify in real-time.

    Args:
        device: soundcard.Microphone object.
        yamnet_model: Loaded YAMNet model.
        classifier: Trained classifier model.
        class_names: List of class names.
        chunk_duration: Duration of each audio chunk in seconds.
        confidence_threshold: Minimum confidence for event detection.
        event_callback: Optional callback function for detected events.
    """
    sample_rate = 16000
    chunk_size = int(chunk_duration * sample_rate)

    # Initialize classifier
    stream_classifier = StreamClassifier(
        yamnet_model=yamnet_model,
        classifier=classifier,
        class_names=class_names,
        sample_rate=sample_rate,
        confidence_threshold=confidence_threshold
    )

    print(f"\nListening to: {device.name}")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Chunk duration: {chunk_duration}s ({chunk_size} samples)")
    print(f"Confidence threshold: {confidence_threshold}")
    print("Press Ctrl+C to stop\n")

    try:
        with device.recorder(samplerate=sample_rate, channels=1) as recorder:
            while True:
                # Record chunk
                audio_chunk = recorder.record(numframes=chunk_size)

                # Flatten to 1D if needed
                if audio_chunk.ndim > 1:
                    audio_chunk = audio_chunk.mean(axis=1)

                # Process chunk
                detections = stream_classifier.process_chunk(audio_chunk)

                # Handle detections
                for detection in detections:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] Event detected: {detection['class']} "
                          f"(confidence: {detection['confidence']:.2f})")

                    if event_callback:
                        event_callback(detection)

    except KeyboardInterrupt:
        print("\n\nStopping listener...")
        stats = stream_classifier.get_stats()
        print(f"\nStatistics:")
        print(f"  Total chunks processed: {stats['total_chunks']}")
        print(f"  Total detections: {stats['total_detections']}")
        print("\nGoodbye!")
