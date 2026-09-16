#!/usr/bin/env bash
# Builds bark-tts-player_<VERSION>_amd64.deb: a self-contained installer that
# bundles the app, the Piper TTS engine, and the voice model, so `dpkg -i` on
# a fresh machine needs no further downloads.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PKG=bark-tts-player
VERSION=1.0.0
ARCH=amd64
STAGE="build/${PKG}_${VERSION}_${ARCH}"

if [ ! -x piper_dist/piper/piper ] || [ ! -f voices/en_US-lessac-medium.onnx ]; then
    echo "Piper binary/voice model missing; running setup.sh first..." >&2
    ./setup.sh
fi

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/opt/$PKG" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/doc/$PKG"

# --- application files ---
cp main.py ui.py tts.py player.py history.py "$STAGE/opt/$PKG/"
cp -r piper_dist voices "$STAGE/opt/$PKG/"
chmod +x "$STAGE/opt/$PKG/piper_dist/piper/piper"

# --- launcher on PATH ---
cat > "$STAGE/usr/bin/$PKG" <<EOF
#!/bin/sh
exec python3 /opt/$PKG/main.py "\$@"
EOF
chmod 755 "$STAGE/usr/bin/$PKG"

# --- icon (hicolor theme, several sizes) ---
python3 - "$STAGE" <<'EOF'
import sys
from pathlib import Path
from PIL import Image

stage = Path(sys.argv[1])
im = Image.open("app.png").convert("RGBA")
w, h = im.size
side = max(w, h)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(im, ((side - w) // 2, (side - h) // 2), im)

for size in (16, 32, 48, 64, 128, 256):
    out_dir = stage / f"usr/share/icons/hicolor/{size}x{size}/apps"
    out_dir.mkdir(parents=True, exist_ok=True)
    square.resize((size, size), Image.LANCZOS).save(out_dir / "bark-tts-player.png")
EOF

# --- desktop entry ---
cat > "$STAGE/usr/share/applications/$PKG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Bark TTS Player
Comment=Type text, hear it spoken, browse playback history
Exec=$PKG
Icon=bark-tts-player
Terminal=false
Categories=AudioVideo;Utility;
EOF

# --- doc/copyright ---
cat > "$STAGE/usr/share/doc/$PKG/copyright" <<'EOF'
This package bundles:
- Piper (https://github.com/rhasspy/piper), MIT License
- The en_US-lessac-medium Piper voice model (https://huggingface.co/rhasspy/piper-voices), MIT License
- espeak-ng-data, distributed with Piper, GPL-3.0

Bark TTS Player application code: written for this project.
EOF

INSTALLED_SIZE=$(du -sk "$STAGE" --exclude=DEBIAN | cut -f1)

# --- control file ---
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: sound
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_SIZE
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-gstreamer-1.0, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good
Recommends: espeak-ng
Maintainer: palash117 <palash2392@gmail.com>
Description: Text-to-speech player with playback history
 Bark TTS Player is a GTK3 desktop app: type text, hear it spoken via an
 offline Piper neural voice (or espeak-ng), control playback with
 play/pause/seek/speed, and browse or replay your speech-clip history.
 All synthesis and playback run locally; no cloud calls, no LLM.
EOF

# --- postinst: refresh icon cache / desktop database (best-effort) ---
cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

cat > "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postrm"

dpkg-deb --build --root-owner-group "$STAGE" "build/${PKG}_${VERSION}_${ARCH}.deb"
echo
echo "Built: build/${PKG}_${VERSION}_${ARCH}.deb"
echo "Install with: sudo apt install ./build/${PKG}_${VERSION}_${ARCH}.deb"
