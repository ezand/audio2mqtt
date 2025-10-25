"""Transfer learning model for audio classification."""

from typing import Tuple

import tensorflow as tf


def extract_embeddings(yamnet_model, waveform: tf.Tensor) -> tf.Tensor:
    """Extract YAMNet embeddings from waveform.

    Args:
        yamnet_model: Loaded YAMNet model.
        waveform: Audio waveform tensor.

    Returns:
        Embeddings tensor of shape (num_frames, 1024).
    """
    scores, embeddings, spectrogram = yamnet_model(waveform)
    return embeddings


def build_classifier(num_classes: int) -> tf.keras.Model:
    """Build transfer learning classifier on top of YAMNet embeddings.

    Args:
        num_classes: Number of output classes.

    Returns:
        Compiled Keras model.
    """
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(1024,), dtype=tf.float32, name='embedding'),
        tf.keras.layers.Dense(512, activation='relu', name='hidden'),
        tf.keras.layers.Dense(num_classes, name='output')
    ], name='audio_classifier')

    model.compile(
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        optimizer='adam',
        metrics=['accuracy']
    )

    return model


def create_combined_model(yamnet_model,
                         classifier: tf.keras.Model,
                         class_names: list) -> tf.keras.Model:
    """Create combined model that takes audio input and outputs class predictions.

    Args:
        yamnet_model: Loaded YAMNet model.
        classifier: Trained classifier model.
        class_names: List of class names.

    Returns:
        Combined Keras model.
    """
    # Input layer for audio waveform
    waveform_input = tf.keras.layers.Input(shape=(), dtype=tf.float32, name='audio')

    # Expand dimensions to match YAMNet expected input
    waveform_expanded = tf.expand_dims(waveform_input, 0)

    # Extract embeddings using YAMNet
    scores, embeddings, spectrogram = yamnet_model(waveform_expanded)

    # Average embeddings across time
    embeddings_mean = tf.reduce_mean(embeddings, axis=0)
    embeddings_mean = tf.expand_dims(embeddings_mean, 0)

    # Get predictions from classifier
    predictions = classifier(embeddings_mean)

    # Create serving model
    serving_model = tf.keras.Model(
        inputs=waveform_input,
        outputs=predictions,
        name='serving_model'
    )

    return serving_model


def predict_class(classifier: tf.keras.Model,
                 embeddings: tf.Tensor,
                 class_names: list) -> Tuple[str, float]:
    """Predict class from embeddings.

    Args:
        classifier: Trained classifier model.
        embeddings: YAMNet embeddings tensor.
        class_names: List of class names.

    Returns:
        Tuple of (predicted_class_name, confidence).
    """
    # Average embeddings across time
    embeddings_mean = tf.reduce_mean(embeddings, axis=0, keepdims=True)

    # Get predictions
    predictions = classifier(embeddings_mean)
    probabilities = tf.nn.softmax(predictions)

    predicted_idx = tf.argmax(probabilities, axis=1).numpy()[0]
    confidence = probabilities.numpy()[0][predicted_idx]

    return class_names[predicted_idx], float(confidence)
