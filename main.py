"""Audio classification using YAMNet model."""

from class_map import load_class_names
from yamnet_classifier import (
    load_yamnet_model,
    load_audio,
    normalize_waveform,
    classify_audio,
    print_audio_info
)


def main() -> None:
    """Run audio classification on a WAV file."""
    # Load model and class names
    yamnet_model = load_yamnet_model()
    class_map_path = yamnet_model.class_map_path().numpy()
    class_names = load_class_names(class_map_path)

    # Load and process audio
    wav_file_name = 'training/mario_dies/death_001.wav'
    sample_rate, wav_data = load_audio(wav_file_name)

    print_audio_info(sample_rate, wav_data)

    # Classify audio
    waveform = normalize_waveform(wav_data)
    inferred_class = classify_audio(yamnet_model, waveform, class_names)
    print(f'The main sound is: {inferred_class}')


if __name__ == "__main__":
    main()
