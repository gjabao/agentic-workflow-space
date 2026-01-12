"""
Sound notification utilities for background task completion.
Plays macOS system sounds when tasks finish.
"""
import subprocess
import sys
from pathlib import Path


def play_sound(sound_name: str = "Glass") -> None:
    """
    Play a macOS system sound.

    Args:
        sound_name: Name of sound file (default: Glass)
                   Options: Basso, Blow, Bottle, Frog, Funk, Glass,
                           Hero, Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink

    Usage:
        play_sound("Glass")  # Success sound
        play_sound("Basso")  # Error sound
    """
    if sys.platform != "darwin":
        return  # Only works on macOS

    sound_path = f"/System/Library/Sounds/{sound_name}.aiff"

    if not Path(sound_path).exists():
        print(f"⚠️ Sound not found: {sound_name}, using default")
        sound_path = "/System/Library/Sounds/Glass.aiff"

    try:
        subprocess.run(
            ["afplay", sound_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
    except Exception:
        pass  # Silently fail if sound can't play


def notify_success() -> None:
    """Play success sound (Glass - pleasant chime)"""
    play_sound("Glass")


def notify_error() -> None:
    """Play error sound (Basso - alert tone)"""
    play_sound("Basso")


def notify_completion() -> None:
    """Play completion sound (Hero - triumphant)"""
    play_sound("Hero")


# Quick test
if __name__ == "__main__":
    print("Testing sounds...")
    print("✓ Success sound:")
    notify_success()

    import time
    time.sleep(1)

    print("✓ Completion sound:")
    notify_completion()

    time.sleep(1)

    print("❌ Error sound:")
    notify_error()
