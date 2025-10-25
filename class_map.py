"""Class map utilities for YAMNet model."""

import csv
from typing import List

import tensorflow as tf


def load_class_names(class_map_csv_path: bytes) -> List[str]:
    """Load class names from CSV file.

    Args:
        class_map_csv_path: Path to the class map CSV file as bytes.

    Returns:
        List of class names corresponding to score vector indices.
    """
    class_names = []
    with tf.io.gfile.GFile(class_map_csv_path) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            class_names.append(row['display_name'])

    return class_names