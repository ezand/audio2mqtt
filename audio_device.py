"""Audio device discovery and selection utilities."""

from typing import List, Optional, Dict, Any
import warnings

import soundcard as sc

# Suppress misleading macOS loopback warning from soundcard library
# BlackHole and other virtual audio devices work fine despite this warning
warnings.filterwarnings('ignore', message='macOS does not support loopback recording functionality')


# Well-known loopback device name patterns
LOOPBACK_PATTERNS = [
    # macOS
    'blackhole',
    'soundflower',

    # Windows
    'wasapi',
    'stereo mix',
    'wave out mix',
    'what u hear',

    # Linux
    'monitor',
]


def list_audio_devices(include_loopback: bool = True) -> List[Dict]:
    """List all available audio input devices.

    Args:
        include_loopback: Include loopback devices in the list.

    Returns:
        List of device info dictionaries with keys: id, name, channels, is_loopback.
    """
    microphones = sc.all_microphones(include_loopback=include_loopback)

    devices = []
    for idx, mic in enumerate(microphones):
        devices.append({
            'id': idx,
            'name': mic.name,
            'channels': mic.channels,
            'is_loopback': mic.isloopback if hasattr(mic, 'isloopback') else False
        })

    return devices


def print_devices(devices: List[Dict]) -> None:
    """Print devices in human-readable format.

    Args:
        devices: List of device dictionaries from list_audio_devices().
    """
    print("\nAvailable audio devices:")
    print("-" * 60)
    for device in devices:
        loopback_indicator = " (loopback)" if device['is_loopback'] else ""
        print(f"  [{device['id']}] {device['name']}{loopback_indicator}")
        print(f"      Channels: {device['channels']}")
    print("-" * 60)


def find_loopback_device(devices: List[Dict]) -> Optional[Dict]:
    """Find first loopback device by checking known patterns.

    Args:
        devices: List of device dictionaries from list_audio_devices().

    Returns:
        Device dictionary if found, None otherwise.
    """
    # First, try devices marked as loopback
    for device in devices:
        if device.get('is_loopback', False):
            return device

    # Fallback: search by name patterns
    for device in devices:
        device_name_lower = device['name'].lower()
        for pattern in LOOPBACK_PATTERNS:
            if pattern in device_name_lower:
                return device

    return None


def find_microphone_device(devices: List[Dict]) -> Optional[Dict]:
    """Find first real microphone device (not loopback).

    Args:
        devices: List of device dictionaries from list_audio_devices().

    Returns:
        Device dictionary if found, None otherwise.
    """
    # Microphone name patterns
    mic_patterns = ['microphone', 'mic', 'input', 'built-in']

    for device in devices:
        # Skip if it's a loopback device
        if device.get('is_loopback', False):
            continue

        device_name_lower = device['name'].lower()

        # Check for microphone patterns
        for pattern in mic_patterns:
            if pattern in device_name_lower:
                return device

    # If no pattern match, return first non-loopback device
    for device in devices:
        if not device.get('is_loopback', False):
            return device

    return None


def select_device(device_id: Optional[int] = None,
                 device_name: Optional[str] = None,
                 auto_select_loopback: bool = True,
                 prefer_microphone: bool = False) -> Optional[Any]:
    """Select audio device for recording.

    Args:
        device_id: Device ID from list_audio_devices().
        device_name: Device name (substring match, case-insensitive).
        auto_select_loopback: If no device specified, auto-select loopback device.
        prefer_microphone: If True, auto-select microphone instead of loopback.

    Returns:
        Microphone object if found, None otherwise.
    """
    devices = list_audio_devices(include_loopback=True)

    # Selection by ID
    if device_id is not None:
        if 0 <= device_id < len(devices):
            microphones = sc.all_microphones(include_loopback=True)
            selected = microphones[device_id]
            print(f"\nSelected device: {selected.name}")
            return selected
        else:
            print(f"Error: Device ID {device_id} out of range (0-{len(devices)-1})")
            return None

    # Selection by name
    if device_name is not None:
        device_name_lower = device_name.lower()
        for device in devices:
            if device_name_lower in device['name'].lower():
                microphones = sc.all_microphones(include_loopback=True)
                selected = microphones[device['id']]
                print(f"\nSelected device: {selected.name}")
                return selected

        print(f"Error: No device found matching '{device_name}'")
        return None

    # Auto-select microphone
    if prefer_microphone:
        mic_device = find_microphone_device(devices)
        if mic_device:
            microphones = sc.all_microphones(include_loopback=True)
            selected = microphones[mic_device['id']]
            print(f"\nAuto-selected microphone: {selected.name}")
            return selected
        else:
            print("\nWarning: No microphone device found.")
            return None

    # Auto-select loopback
    if auto_select_loopback:
        loopback_device = find_loopback_device(devices)
        if loopback_device:
            microphones = sc.all_microphones(include_loopback=True)
            selected = microphones[loopback_device['id']]
            print(f"\nAuto-selected loopback device: {selected.name}")
            return selected
        else:
            print("\nWarning: No loopback device found.")
            print("Please install a virtual audio device:")
            print("  macOS: BlackHole (https://github.com/ExistentialAudio/BlackHole)")
            print("  Windows: VB-CABLE or enable 'Stereo Mix'")
            print("  Linux: PulseAudio monitor")
            return None

    return None


def get_device_info(device: Any) -> Dict:
    """Get detailed information about an audio device.

    Args:
        device: Microphone object.

    Returns:
        Dictionary with device information.
    """
    return {
        'name': device.name,
        'channels': device.channels,
        'is_loopback': device.isloopback if hasattr(device, 'isloopback') else False,
    }


def main():
    """CLI for listing and testing audio devices."""
    print("\n" + "="*60)
    print("Audio Device Discovery")
    print("="*60)
    print("\nNote: On macOS, 'loopback' requires a virtual audio device")
    print("like BlackHole. The soundcard library may show a warning,")
    print("but virtual loopback devices work perfectly fine.\n")

    devices = list_audio_devices(include_loopback=True)
    print_devices(devices)

    loopback = find_loopback_device(devices)
    microphone = find_microphone_device(devices)

    print("\nAuto-detection results:")
    if loopback:
        print(f"  ✓ Loopback device: {loopback['name']}")
    else:
        print("  ✗ No loopback device found")
        print("    To enable system audio capture:")
        print("      macOS: Install BlackHole (https://github.com/ExistentialAudio/BlackHole)")
        print("      Windows: Enable 'Stereo Mix' or install VB-CABLE")
        print("      Linux: Use PulseAudio monitor")

    if microphone:
        print(f"  ✓ Microphone device: {microphone['name']}")
    else:
        print("  ✗ No microphone device found")


if __name__ == "__main__":
    main()
