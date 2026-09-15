"""Text-to-speech backends: a neural voice (Piper) and a classic
formant-synthesis voice (espeak-ng). Neither is a language model — both take
already-written text and render it as audio, with no text generation or
understanding involved.
"""
import os
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PIPER_DIR = BASE_DIR / "piper_dist" / "piper"
PIPER_BIN = PIPER_DIR / "piper"
PIPER_ESPEAK_DATA = PIPER_DIR / "espeak-ng-data"
VOICES_DIR = BASE_DIR / "voices"

# label -> (engine, voice identifier)
# "piper" identifiers are onnx model filenames under VOICES_DIR.
# "espeak" identifiers are espeak-ng -v values.
VOICE_OPTIONS = {
    "Piper - Lessac (natural)": ("piper", "en_US-lessac-medium.onnx"),
    "espeak-ng - US Female (soft)": ("espeak", "en-us+f3"),
    "espeak-ng - US Male (soft)": ("espeak", "en-us+m3"),
    "espeak-ng - British Female": ("espeak", "en-gb+f3"),
    "espeak-ng - British Male (RP)": ("espeak", "en-gb-x-rp+m3"),
    "espeak-ng - US Default (robotic)": ("espeak", "en-us"),
}
DEFAULT_VOICE = "Piper - Lessac (natural)"

# espeak-ng only; ignored for Piper voices.
DEFAULT_SPEED = 150      # words per minute
DEFAULT_PITCH = 42       # 0-99
DEFAULT_AMPLITUDE = 160  # 0-200


class TTSError(Exception):
    pass


def synthesize_to_wav(
    text: str,
    out_path: str,
    voice_label: str = DEFAULT_VOICE,
    speed: int = DEFAULT_SPEED,
    pitch: int = DEFAULT_PITCH,
    amplitude: int = DEFAULT_AMPLITUDE,
) -> None:
    text = text.strip()
    if not text:
        raise TTSError("Text is empty.")

    engine, voice_id = VOICE_OPTIONS.get(voice_label, VOICE_OPTIONS[DEFAULT_VOICE])
    if engine == "piper":
        _synthesize_piper(text, out_path, voice_id)
    else:
        _synthesize_espeak(text, out_path, voice_id, speed, pitch, amplitude)


def _synthesize_piper(text: str, out_path: str, model_filename: str) -> None:
    model_path = VOICES_DIR / model_filename
    if not PIPER_BIN.exists():
        raise TTSError(f"Piper binary not found at {PIPER_BIN}")
    if not model_path.exists():
        raise TTSError(f"Piper voice model not found at {model_path}")

    env = dict(os.environ, LD_LIBRARY_PATH=str(PIPER_DIR))
    try:
        subprocess.run(
            [
                str(PIPER_BIN),
                "--model", str(model_path),
                "--espeak_data", str(PIPER_ESPEAK_DATA),
                "--output_file", out_path,
            ],
            input=text,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        raise TTSError(f"piper failed: {exc.stderr.strip()}") from exc


def _synthesize_espeak(
    text: str, out_path: str, voice: str, speed: int, pitch: int, amplitude: int
) -> None:
    if shutil.which("espeak-ng") is None:
        raise TTSError(
            "espeak-ng is not installed. Install it with: sudo apt-get install -y espeak-ng"
        )
    try:
        subprocess.run(
            [
                "espeak-ng",
                "-v", voice,
                "-s", str(speed),
                "-p", str(pitch),
                "-a", str(amplitude),
                "-g", "8",
                "-w", out_path,
                text,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise TTSError(f"espeak-ng failed: {exc.stderr.strip()}") from exc
