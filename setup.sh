#!/usr/bin/env bash
# Downloads the Piper TTS engine + a voice model that main.py expects at
# ./piper_dist/piper/piper and ./voices/en_US-lessac-medium.onnx.
# These are large binary downloads, so they are not committed to git.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ "$(uname -m)" != "x86_64" ]; then
    echo "This script downloads the x86_64 Piper build; edit PIPER_URL for other architectures." >&2
    exit 1
fi

PIPER_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
VOICE_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"

if [ ! -x piper_dist/piper/piper ]; then
    echo "Downloading Piper TTS engine..."
    mkdir -p piper_dist
    curl -sL --retry 3 --max-time 180 -o piper_dist/piper.tar.gz "$PIPER_URL"
    tar xzf piper_dist/piper.tar.gz -C piper_dist
    rm piper_dist/piper.tar.gz
    chmod +x piper_dist/piper/piper
else
    echo "Piper binary already present, skipping."
fi

if [ ! -f voices/en_US-lessac-medium.onnx ]; then
    echo "Downloading Piper voice model (en_US-lessac-medium, ~61MB)..."
    mkdir -p voices
    curl -sL --retry 3 --max-time 120 -o voices/en_US-lessac-medium.onnx "$VOICE_BASE/en_US-lessac-medium.onnx"
    curl -sL --retry 3 --max-time 60 -o voices/en_US-lessac-medium.onnx.json "$VOICE_BASE/en_US-lessac-medium.onnx.json"
else
    echo "Voice model already present, skipping."
fi

if ! command -v espeak-ng >/dev/null 2>&1; then
    echo
    echo "Note: espeak-ng is not installed. It's only needed for the espeak-ng"
    echo "voice options (Piper works without it). Install it with:"
    echo "  sudo apt-get install -y espeak-ng"
fi

echo
echo "Setup complete. Run the app with: python3 main.py"
