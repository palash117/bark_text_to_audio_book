#!/usr/bin/env python3
"""Bark TTS Player: text -> speech, with playback controls and history."""
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ui import BarkWindow


class BarkApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.bark.TTSPlayer")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = BarkWindow(self)
        win.present()


if __name__ == "__main__":
    app = BarkApplication()
    sys.exit(app.run(sys.argv))
