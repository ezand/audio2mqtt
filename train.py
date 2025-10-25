"""Training script for custom audio classifier."""

import os
import sys
from pathlib import Path

import tensorflow as tf

from dataset import create_dataset
from model import build_classifier, extract_embeddings
from yamnet_classifier import load_yamnet_model


def extract_embeddings_from_dataset(yamnet_model, dataset):
    """Extract YAMNet embeddings from entire dataset.

    Args:
        yamnet_model: Loaded YAMNet model.
        dataset: TensorFlow dataset of (waveform, label) pairs.

    Returns:
        Dataset of (embedding, label) pairs.
    """
    all_embeddings = []
    all_labels = []

    # Process dataset eagerly
    for waveforms, labels in dataset:
        # Process each waveform in the batch
        for i in range(waveforms.shape[0]):
            waveform = waveforms[i]
            label = labels[i]

            # Extract embeddings for this waveform
            embeddings = extract_embeddings(yamnet_model, waveform)

            # Store all embedding frames with repeated labels
            num_frames = embeddings.shape[0]
            all_embeddings.append(embeddings)
            all_labels.extend([label.numpy()] * num_frames)

    # Concatenate all embeddings
    all_embeddings = tf.concat(all_embeddings, axis=0)
    all_labels = tf.constant(all_labels, dtype=tf.int32)

    # Create new dataset from embeddings
    embeddings_dataset = tf.data.Dataset.from_tensor_slices((all_embeddings, all_labels))
    embeddings_dataset = embeddings_dataset.shuffle(1000)
    embeddings_dataset = embeddings_dataset.batch(32)
    embeddings_dataset = embeddings_dataset.prefetch(tf.data.AUTOTUNE)

    return embeddings_dataset


def train(training_dir: str = 'training',
         output_dir: str = 'models',
         epochs: int = 50,
         batch_size: int = 16) -> None:
    """Train audio classifier.

    Args:
        training_dir: Directory containing training data.
        output_dir: Directory to save trained model.
        epochs: Number of training epochs.
        batch_size: Batch size for training.
    """
    print("Loading YAMNet model...")
    yamnet_model = load_yamnet_model()

    print(f"Loading training data from {training_dir}...")
    dataset, class_names = create_dataset(training_dir, batch_size=batch_size)

    print(f"Found {len(class_names)} classes: {class_names}")

    # Count samples
    total_samples = sum(1 for _ in dataset)
    print(f"Total batches: {total_samples}")

    # Recreate dataset (consumed by count)
    dataset, _ = create_dataset(training_dir, batch_size=batch_size)

    print("Extracting embeddings from training data...")
    embeddings_dataset = extract_embeddings_from_dataset(yamnet_model, dataset)

    print("Building classifier...")
    classifier = build_classifier(num_classes=len(class_names))
    classifier.summary()

    print(f"\nTraining for {epochs} epochs...")
    history = classifier.fit(
        embeddings_dataset,
        epochs=epochs,
        verbose=1
    )

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Save classifier
    classifier_path = output_path / 'classifier.keras'
    print(f"\nSaving classifier to {classifier_path}...")
    classifier.save(classifier_path)

    # Save class names
    class_names_path = output_path / 'class_names.txt'
    print(f"Saving class names to {class_names_path}...")
    with open(class_names_path, 'w') as f:
        f.write('\n'.join(class_names))

    print("\nTraining complete!")
    print(f"Final training accuracy: {history.history['accuracy'][-1]:.4f}")


def main() -> None:
    """Main training entry point."""
    if len(sys.argv) > 1:
        training_dir = sys.argv[1]
    else:
        training_dir = 'training'

    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    else:
        output_dir = 'models'

    train(training_dir=training_dir, output_dir=output_dir)


if __name__ == "__main__":
    main()
