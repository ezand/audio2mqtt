"""Audio classification using YAMNet model."""

import sys
from pathlib import Path

import tensorflow as tf

from class_map import load_class_names
from model import extract_embeddings, predict_class
from yamnet_classifier import (
    load_yamnet_model,
    load_audio,
    normalize_waveform,
    classify_audio,
    print_audio_info
)


def classify_with_custom_model(wav_file: str,
                               classifier_path: str = 'models/classifier.keras',
                               class_names_path: str = 'models/class_names.txt') -> None:
    """Classify audio using custom trained model.

    Args:
        wav_file: Path to WAV file to classify.
        classifier_path: Path to saved classifier model.
        class_names_path: Path to class names file.
    """
    # Check if model exists
    if not Path(classifier_path).exists():
        print(f"Error: Classifier not found at {classifier_path}")
        print("Train a model first using: python train.py")
        sys.exit(1)

    # Load models and class names
    print("Loading models...")
    yamnet_model = load_yamnet_model()
    classifier = tf.keras.models.load_model(classifier_path)

    with open(class_names_path, 'r') as f:
        class_names = [line.strip() for line in f.readlines()]

    # Load and process audio
    print(f"\nClassifying: {wav_file}")
    sample_rate, wav_data = load_audio(wav_file)
    print_audio_info(sample_rate, wav_data)

    # Extract embeddings and classify
    waveform = normalize_waveform(wav_data)
    embeddings = extract_embeddings(yamnet_model, waveform)
    predicted_class, confidence = predict_class(classifier, embeddings, class_names)

    print(f'\nPredicted class: {predicted_class}')
    print(f'Confidence: {confidence:.2%}')


def classify_with_base_yamnet(wav_file: str) -> None:
    """Classify audio using base YAMNet model.

    Args:
        wav_file: Path to WAV file to classify.
    """
    # Load model and class names
    yamnet_model = load_yamnet_model()
    class_map_path = yamnet_model.class_map_path().numpy()
    class_names = load_class_names(class_map_path)

    # Load and process audio
    print(f"Classifying: {wav_file}")
    sample_rate, wav_data = load_audio(wav_file)
    print_audio_info(sample_rate, wav_data)

    # Classify audio
    waveform = normalize_waveform(wav_data)
    inferred_class = classify_audio(yamnet_model, waveform, class_names)
    print(f'The main sound is: {inferred_class}')


def main() -> None:
    """Run audio classification on a WAV file."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <wav_file> [--custom]")
        print("  --custom: Use custom trained model (default: base YAMNet)")
        sys.exit(1)

    wav_file = sys.argv[1]
    use_custom = '--custom' in sys.argv

    if not Path(wav_file).exists():
        print(f"Error: File not found: {wav_file}")
        sys.exit(1)

    if use_custom:
        classify_with_custom_model(wav_file)
    else:
        classify_with_base_yamnet(wav_file)


if __name__ == "__main__":
    main()
