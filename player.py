"""GStreamer-backed audio player with play/pause/seek support."""
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

Gst.init(None)


class Player:
    def __init__(self, on_eos=None, on_error=None):
        self._pipeline = Gst.ElementFactory.make("playbin", "player")
        scaletempo = Gst.ElementFactory.make("scaletempo", None)
        if scaletempo:
            # Keeps pitch natural when playback rate != 1.0.
            self._pipeline.set_property("audio-filter", scaletempo)
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_message)
        self._on_eos = on_eos
        self._on_error = on_error
        self._duration_ns = 0
        self._rate = 1.0

    def load(self, path: str) -> float:
        """Load a file, pause on it, and return its duration in seconds."""
        self._pipeline.set_state(Gst.State.NULL)
        uri = Gst.filename_to_uri(path)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PAUSED)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)  # block until prerolled
        ok, dur = self._pipeline.query_duration(Gst.Format.TIME)
        self._duration_ns = dur if ok else 0
        if self._rate != 1.0:
            self._seek(self._rate, 0)  # re-apply the chosen speed to the new media
        return self.get_duration_seconds()

    def play(self):
        self._pipeline.set_state(Gst.State.PLAYING)

    def pause(self):
        self._pipeline.set_state(Gst.State.PAUSED)

    def toggle(self):
        if self.is_playing():
            self.pause()
        else:
            self.play()

    def is_playing(self) -> bool:
        _, state, _ = self._pipeline.get_state(0)
        return state == Gst.State.PLAYING

    def seek_to_seconds(self, seconds: float):
        ns = max(0, int(seconds * Gst.SECOND))
        self._seek(self._rate, ns)

    def set_rate(self, rate: float):
        """Change playback speed (1.0 = normal), keeping the current position."""
        self._rate = rate
        ok, pos_ns = self._pipeline.query_position(Gst.Format.TIME)
        self._seek(rate, pos_ns if ok else 0)

    def get_rate(self) -> float:
        return self._rate

    def _seek(self, rate: float, position_ns: int):
        self._pipeline.seek(
            rate,
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
            Gst.SeekType.SET, position_ns,
            Gst.SeekType.NONE, -1,
        )

    def get_position_seconds(self) -> float:
        ok, pos = self._pipeline.query_position(Gst.Format.TIME)
        return (pos / Gst.SECOND) if ok else 0.0

    def get_duration_seconds(self) -> float:
        return (self._duration_ns / Gst.SECOND) if self._duration_ns else 0.0

    def stop(self):
        self._pipeline.set_state(Gst.State.NULL)

    def _on_message(self, _bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self._pipeline.set_state(Gst.State.PAUSED)
            self.seek_to_seconds(0)
            if self._on_eos:
                self._on_eos()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            if self._on_error:
                self._on_error(f"{err.message} ({debug})")
