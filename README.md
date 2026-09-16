# Bark TTS Player

A GTK3 desktop app for Ubuntu: type text, hear it spoken, and browse/replay
past clips. Text-to-speech runs entirely offline via [Piper](https://github.com/rhasspy/piper)
(a small neural voice model, not a language model) or [espeak-ng](https://github.com/espeak-ng/espeak-ng)
as a fallback. No LLM, no cloud calls.

Three panes:
1. **Text input** — type text, hit Submit, pick a voice/speed/pitch.
2. **Now playing** — play/pause, seek bar, elapsed/total time, playback speed
   (0.5x-2.0x, pitch preserved via GStreamer's `scaletempo`).
3. **History** — every generated clip, click to replay, or delete it.

## Setup

Requires Python 3 with GTK3/GStreamer bindings (`python3-gi`, `gir1.2-gtk-3.0`,
`gir1.2-gstreamer-1.0` and the `gstreamer1.0-plugins-*` set — installed by
default on most Ubuntu desktops).

```bash
git clone https://github.com/palash117/bark_text_to_audio_book.git
cd bark_text_to_audio_book
./setup.sh          # downloads the Piper binary + voice model (~113MB)
python3 main.py
```

For the espeak-ng voice options (optional, Piper works without it):

```bash
sudo apt-get install -y espeak-ng
```

## Debian package

To build a self-contained `.deb` (bundles Piper + the voice model, so
installing it needs no further downloads):

```bash
./build_deb.sh
sudo apt install ./build/bark-tts-player_1.0.0_amd64.deb
```

This installs the app to `/opt/bark-tts-player`, adds a `bark-tts-player`
launcher to your `PATH`, and registers it in the application menu using
`app.png` as the icon.

## Files

- `main.py` — entry point
- `ui.py` — the three-pane GTK3 layout
- `tts.py` — Piper / espeak-ng synthesis
- `player.py` — GStreamer playback (play/pause/seek/speed)
- `history.py` — JSON-backed clip history (`~/.local/share/bark-tts/`)
- `setup.sh` — downloads Piper + voice model (not committed; see `.gitignore`)
- `build_deb.sh` — builds a self-contained Debian package (`build/*.deb`, not committed)
- `app.png` — app icon, used both by `bark.desktop` and the Debian package
- `bark.desktop` — optional app-menu launcher (for a non-packaged checkout)
