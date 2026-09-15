"""Three-pane GTK3 UI: text input, now-playing controls, history."""
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from history import HistoryStore
from player import Player
from tts import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_VOICE,
    VOICE_OPTIONS,
    TTSError,
    synthesize_to_wav,
)


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


SPEED_PRESETS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
DEFAULT_SPEED_INDEX = SPEED_PRESETS.index(1.0)


class BarkWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Bark TTS Player")
        self.set_default_size(1100, 620)

        self.history_store = HistoryStore()
        self.player = Player(on_eos=self._on_eos, on_error=self._on_player_error)
        self._current_entry = None
        self._user_seeking = False
        self._speed_index = DEFAULT_SPEED_INDEX

        outer = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        inner = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        outer.pack1(self._build_input_pane(), True, False)
        outer.pack2(inner, True, False)
        inner.pack1(self._build_player_pane(), True, False)
        inner.pack2(self._build_history_pane(), True, False)
        outer.set_position(340)
        inner.set_position(380)

        self.add(outer)
        self._load_history_into_listbox()
        self.show_all()
        GLib.timeout_add(250, self._update_progress)

    # ---------- Pane 1: text input ----------
    def _build_input_pane(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        label = Gtk.Label(label="Text to speak", xalign=0)
        box.pack_start(label, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        scroller.add(self.textview)
        box.pack_start(scroller, True, True, 0)

        submit_btn = Gtk.Button(label="Submit")
        submit_btn.connect("clicked", self._on_submit_clicked)
        box.pack_start(submit_btn, False, False, 0)

        box.pack_start(self._build_voice_settings(), False, False, 0)

        self.error_label = Gtk.Label(label="", xalign=0)
        self.error_label.set_line_wrap(True)
        box.pack_start(self.error_label, False, False, 0)

        return box

    def _build_voice_settings(self) -> Gtk.Widget:
        expander = Gtk.Expander(label="Voice settings")
        grid = Gtk.Grid(row_spacing=4, column_spacing=8)
        grid.set_margin_top(6)

        grid.attach(Gtk.Label(label="Voice", xalign=0), 0, 0, 1, 1)
        self.voice_combo = Gtk.ComboBoxText()
        for name in VOICE_OPTIONS:
            self.voice_combo.append(name, name)
        self.voice_combo.set_active_id(DEFAULT_VOICE)
        grid.attach(self.voice_combo, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Speed (espeak-ng only)", xalign=0), 0, 1, 1, 1)
        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 80, 300, 5)
        self.speed_scale.set_value(DEFAULT_SPEED)
        self.speed_scale.set_hexpand(True)
        grid.attach(self.speed_scale, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label="Pitch (espeak-ng only)", xalign=0), 0, 2, 1, 1)
        self.pitch_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 99, 1)
        self.pitch_scale.set_value(DEFAULT_PITCH)
        self.pitch_scale.set_hexpand(True)
        grid.attach(self.pitch_scale, 1, 2, 1, 1)

        expander.add(grid)
        return expander

    def _on_submit_clicked(self, _button):
        buf = self.textview.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, True).strip()
        if not text:
            return

        voice_label = self.voice_combo.get_active_id() or DEFAULT_VOICE
        speed = int(self.speed_scale.get_value())
        pitch = int(self.pitch_scale.get_value())

        out_path = self.history_store.new_audio_path()
        try:
            synthesize_to_wav(
                text, str(out_path), voice_label=voice_label, speed=speed, pitch=pitch
            )
        except TTSError as exc:
            self.error_label.set_text(str(exc))
            return
        self.error_label.set_text("")

        duration = self.player.load(str(out_path))
        entry = self.history_store.add_entry(text, str(out_path), duration)
        self._start_playing_entry(entry, duration, already_loaded=True)
        self._prepend_history_row(entry)
        buf.set_text("")

    # ---------- Pane 2: now playing ----------
    def _build_player_pane(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        title = Gtk.Label(label="Now Playing", xalign=0)
        box.pack_start(title, False, False, 0)

        self.now_playing_label = Gtk.Label(label="(nothing yet)", xalign=0)
        self.now_playing_label.set_line_wrap(True)
        box.pack_start(self.now_playing_label, False, False, 0)

        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.scale.set_draw_value(False)
        self.scale.set_hexpand(True)
        self.scale.connect("button-press-event", self._on_scale_press)
        self.scale.connect("button-release-event", self._on_scale_release)
        box.pack_start(self.scale, False, False, 0)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.playpause_btn = Gtk.Button(label="Play")
        self.playpause_btn.connect("clicked", self._on_playpause_clicked)
        self.playpause_btn.set_sensitive(False)
        controls.pack_start(self.playpause_btn, False, False, 0)

        self.time_label = Gtk.Label(label="0:00 / 0:00")
        controls.pack_start(self.time_label, False, False, 0)

        self.speed_btn = Gtk.Button(label=f"Speed: {SPEED_PRESETS[self._speed_index]}x")
        self.speed_btn.connect("clicked", self._on_speed_clicked)
        controls.pack_start(self.speed_btn, False, False, 0)

        box.pack_start(controls, False, False, 0)

        self.player_error_label = Gtk.Label(label="", xalign=0)
        self.player_error_label.set_line_wrap(True)
        box.pack_start(self.player_error_label, False, False, 0)

        return box

    def _start_playing_entry(self, entry, duration, already_loaded=False):
        if not already_loaded:
            duration = self.player.load(entry["filepath"])
        self._current_entry = entry
        self.player.play()
        preview = truncate(entry["text"], 90)
        self.now_playing_label.set_text(f'"{preview}"\n{Path(entry["filepath"]).name}')
        self.scale.set_range(0, max(duration, 0.01))
        self.scale.set_value(0)
        self.time_label.set_text(f"0:00 / {format_time(duration)}")
        self.playpause_btn.set_sensitive(True)
        self._refresh_playpause_label()

    def _on_playpause_clicked(self, _button):
        if not self._current_entry:
            return
        self.player.toggle()
        self._refresh_playpause_label()

    def _refresh_playpause_label(self):
        self.playpause_btn.set_label("Pause" if self.player.is_playing() else "Play")

    def _on_speed_clicked(self, _button):
        self._speed_index = (self._speed_index + 1) % len(SPEED_PRESETS)
        rate = SPEED_PRESETS[self._speed_index]
        self.speed_btn.set_label(f"Speed: {rate}x")
        if self._current_entry:
            self.player.set_rate(rate)

    def _on_scale_press(self, _widget, _event):
        self._user_seeking = True

    def _on_scale_release(self, _widget, _event):
        self._user_seeking = False
        if self._current_entry:
            self.player.seek_to_seconds(self.scale.get_value())

    def _update_progress(self):
        if self._current_entry and not self._user_seeking:
            pos = self.player.get_position_seconds()
            dur = self.player.get_duration_seconds() or self.scale.get_upper()
            self.scale.set_value(pos)
            self.time_label.set_text(f"{format_time(pos)} / {format_time(dur)}")
        return True

    def _on_eos(self):
        GLib.idle_add(self._handle_eos)

    def _handle_eos(self):
        self._refresh_playpause_label()
        self.scale.set_value(0)
        dur = self.player.get_duration_seconds() or self.scale.get_upper()
        self.time_label.set_text(f"0:00 / {format_time(dur)}")
        return False

    def _on_player_error(self, message):
        GLib.idle_add(self.player_error_label.set_text, message)

    # ---------- Pane 3: history ----------
    def _build_history_pane(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        title = Gtk.Label(label="History", xalign=0)
        box.pack_start(title, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.listbox = Gtk.ListBox()
        self.listbox.connect("row-activated", self._on_history_row_activated)
        scroller.add(self.listbox)
        box.pack_start(scroller, True, True, 0)

        return box

    def _make_history_row(self, entry: dict) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox.set_margin_start(6)
        hbox.set_margin_end(6)
        hbox.set_margin_top(4)
        hbox.set_margin_bottom(4)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ts_label = Gtk.Label(label=entry["timestamp"], xalign=0)
        vbox.pack_start(ts_label, False, False, 0)

        text_label = Gtk.Label(label=truncate(entry["text"], 60), xalign=0)
        text_label.set_line_wrap(True)
        vbox.pack_start(text_label, False, False, 0)
        hbox.pack_start(vbox, True, True, 0)

        delete_btn = Gtk.Button(label="Delete")
        delete_btn.connect("clicked", self._on_delete_entry_clicked, entry, row)
        hbox.pack_start(delete_btn, False, False, 0)

        row.add(hbox)
        row.entry = entry
        row.show_all()
        return row

    def _on_delete_entry_clicked(self, _button, entry, row):
        self.history_store.remove_entry(entry["id"])
        self.listbox.remove(row)
        if self._current_entry and self._current_entry["id"] == entry["id"]:
            self.player.stop()
            self._current_entry = None
            self.now_playing_label.set_text("(nothing yet)")
            self.scale.set_range(0, 1)
            self.scale.set_value(0)
            self.time_label.set_text("0:00 / 0:00")
            self.playpause_btn.set_sensitive(False)
            self._refresh_playpause_label()

    def _prepend_history_row(self, entry: dict):
        row = self._make_history_row(entry)
        self.listbox.insert(row, 0)

    def _load_history_into_listbox(self):
        for entry in self.history_store.list_entries():
            self.listbox.add(self._make_history_row(entry))

    def _on_history_row_activated(self, _listbox, row):
        self._start_playing_entry(row.entry, duration=None, already_loaded=False)
