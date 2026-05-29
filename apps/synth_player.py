"""Synth Player — plays a synth version of the current Spotify track."""

import time
import json
import math
import random

import M5
from hardware import MatrixKeyboard

_LCD = M5.Lcd
_SPK = M5.Speaker

_W = 240
_H = 135

_BLACK   = 0x000000
_DARK    = 0x1F1F1F
_WHITE   = 0xFFFFFF
_GRAY    = 0x777777
_GREEN   = 0x1DB954
_DGRAY   = 0x444444
_MAGENTA = 0xDD44DD

# Note colors — one per semitone (same as synth.py)
_COLORS = [
    0xFF4444, 0xFF7744, 0xFFAA33, 0xFFDD22,
    0xEEEE00, 0x44DD44, 0x22CCAA, 0x3399FF,
    0x6666FF, 0x9944FF, 0xDD44DD, 0xFF4499,
]

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
               "F#", "G", "G#", "A", "A#", "B"]

_PROXY = "https://riwashouse.live"

# Playback state
_notes = []
_note_idx = 0
_note_start = 0
_paused = False
_track = ""
_artist = ""

# Ripple state
_ripples = []
_tick = 0


def _freq_to_note(freq):
    """Return (note_index_0_23, note_name, octave) for a frequency."""
    if freq <= 0:
        return -1, "", ""
    midi = round(69 + 12 * math.log(freq / 440) / math.log(2))
    idx = max(0, min(23, int(midi) - 60))
    name = _NOTE_NAMES[idx % 12]
    octave = str(4 + idx // 12)
    return idx, name, octave


def _http_request(url, method="GET", timeout=10):
    """HTTP/HTTPS request with configurable timeout."""
    import socket
    import ssl

    is_https = url.startswith("https://")
    url_body = url.replace("https://", "").replace("http://", "")

    if "/" in url_body:
        host_port, path = url_body.split("/", 1)
        path = "/" + path
    else:
        host_port = url_body
        path = "/"

    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 443 if is_https else 80

    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        if is_https:
            s = ssl.wrap_socket(s, server_hostname=host)

        content_length = "Content-Length: 0\r\n" if method == "POST" else ""
        req = "{} {} HTTP/1.0\r\nHost: {}\r\n{}Connection: close\r\n\r\n".format(
            method, path, host, content_length)
        s.write(req.encode()) if is_https else s.send(req.encode())

        response = b""
        while True:
            try:
                chunk = s.read(4096) if is_https else s.recv(4096)
                if not chunk:
                    break
                response += chunk
            except:
                break

        parts = response.split(b"\r\n\r\n", 1)
        if len(parts) == 2 and parts[1]:
            return json.loads(parts[1])
        return {}
    except:
        return None
    finally:
        s.close()


def _draw_chrome():
    _LCD.fillScreen(_BLACK)
    _LCD.fillRect(0, 0, _W, 17, _DARK)
    _LCD.fillRect(0, 17, _W, 1, _MAGENTA)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_MAGENTA, _DARK)
    _LCD.drawString("Synth Play", 6, 4)

    _LCD.fillRect(0, _H - 17, _W, 17, _DARK)
    _LCD.setTextColor(_GRAY, _DARK)
    hint = "<prev  space:pause  >next  ESC"
    _LCD.drawString(hint, (_W - _LCD.textWidth(hint)) // 2, _H - 13)


def _draw_track_info():
    _LCD.fillRect(0, 20, _W, 14, _BLACK)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_WHITE, _BLACK)
    info = _track
    if _artist:
        info = _track + " - " + _artist
    if len(info) > 38:
        info = info[:36] + ".."
    _LCD.drawString(info, 6, 22)


def _draw_loading():
    _LCD.fillRect(0, 20, _W, _H - 37, _BLACK)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GRAY, _BLACK)
    msg = "Loading synth..."
    _LCD.drawString(msg, (_W - _LCD.textWidth(msg)) // 2, 65)


def _draw_error(msg):
    _LCD.fillRect(0, 20, _W, _H - 37, _BLACK)
    _LCD.setTextSize(1)
    _LCD.setTextColor(0xFF4444, _BLACK)
    _LCD.drawString(msg[:34], (_W - _LCD.textWidth(msg[:34])) // 2, 55)
    _LCD.setTextColor(_GRAY, _BLACK)
    hint = "Press > to try next track"
    _LCD.drawString(hint, (_W - _LCD.textWidth(hint)) // 2, 75)


def _draw_progress():
    """Draw a progress bar showing position in the note sequence."""
    bar_y = 104
    bar_w = _W - 20
    _LCD.fillRect(10, bar_y, bar_w, 4, _DGRAY)
    if _notes:
        filled = (_note_idx * bar_w) // len(_notes)
        if filled > 0:
            _LCD.fillRect(10, bar_y, filled, 4, _MAGENTA)


def _draw_pause_indicator():
    _LCD.setTextSize(1)
    _LCD.setTextColor(_MAGENTA, _DARK)
    indicator = "PAUSED" if _paused else "      "
    _LCD.drawString(indicator, _W - 50, 4)


def _spawn_ripple(note_idx):
    x = 10 + (note_idx * (_W - 20)) // 23
    y = 50 + random.randint(0, 30)
    color = _COLORS[note_idx % 12]
    _ripples.append([x, y, 3, color, _tick])


def _draw_ripples():
    global _ripples
    alive = []
    for r in _ripples:
        x, y, radius, color, birth = r
        age = _tick - birth
        if age > 15:
            _LCD.drawCircle(x, y, radius, _BLACK)
            continue
        if radius > 3:
            _LCD.drawCircle(x, y, radius - 2, _BLACK)
        radius = 3 + age * 3
        r[2] = radius
        if y - radius > 34 and y + radius < 100:
            _LCD.drawCircle(x, y, radius, color)
        alive.append(r)
    _ripples = alive


def _draw_note_name(note_idx, name, octave):
    color = _COLORS[note_idx % 12]
    _LCD.fillRect(85, 70, 70, 20, _BLACK)
    _LCD.setTextSize(2)
    _LCD.setTextColor(color, _BLACK)
    text = name + octave
    _LCD.drawString(text, (_W - _LCD.textWidth(text)) // 2, 72)


def _clear_note_name():
    _LCD.fillRect(85, 70, 70, 20, _BLACK)


def _fetch_synth_data():
    """Fetch synth note data from the proxy."""
    global _notes, _track, _artist

    data = _http_request(_PROXY + "/synth-preview", timeout=15)

    if data is None:
        _notes = []
        _track = ""
        _artist = ""
        return "Can't reach proxy"

    if not data.get("ok"):
        _notes = []
        err = data.get("error", "unknown")
        if err == "no_preview":
            return "No preview for this track"
        if err == "not_playing":
            return "Nothing playing"
        if err == "not_authorized":
            return "Visit /login on proxy"
        return "Error: " + err

    _notes = data.get("notes", [])
    _track = data.get("track", "")
    _artist = data.get("artist", "")
    return None  # success


def run():
    global _notes, _note_idx, _note_start, _paused, _tick
    global _track, _artist, _ripples

    _notes = []
    _note_idx = 0
    _paused = False
    _tick = 0
    _ripples = []

    try:
        _SPK.begin()
        _SPK.setVolume(80)
    except:
        pass

    _draw_chrome()
    _draw_loading()

    err = _fetch_synth_data()
    if err:
        _draw_error(err)
        kb = MatrixKeyboard()
        time.sleep_ms(300)
        while True:
            kb.tick()
            k = kb.get_key()
            if k is not None:
                code = k if isinstance(k, int) else ord(k) if isinstance(k, str) else None
                if code == 0x1B:
                    _LCD.fillScreen(_BLACK)
                    return
                if code in (0xB7, ord('d'), ord('.')):
                    _http_request(_PROXY + "/next", "POST")
                    time.sleep_ms(500)
                    _draw_loading()
                    err = _fetch_synth_data()
                    if not err:
                        break
                    _draw_error(err)
                if code in (0xB4, ord('a'), ord(',')):
                    _http_request(_PROXY + "/prev", "POST")
                    time.sleep_ms(500)
                    _draw_loading()
                    err = _fetch_synth_data()
                    if not err:
                        break
                    _draw_error(err)
            time.sleep_ms(40)

    # Start playback
    _draw_chrome()
    _draw_track_info()
    _note_idx = 0
    _note_start = time.ticks_ms()

    # Play first note
    if _notes:
        freq = _notes[0][0]
        dur = _notes[0][1]
        if freq > 0:
            try:
                _SPK.tone(freq, dur)
            except:
                pass
            idx, name, octave = _freq_to_note(freq)
            if idx >= 0:
                _spawn_ripple(idx)
                _draw_note_name(idx, name, octave)
        _draw_progress()

    kb = MatrixKeyboard()
    time.sleep_ms(300)

    while True:
        kb.tick()
        k = kb.get_key()

        if k is not None:
            code = k if isinstance(k, int) else ord(k) if isinstance(k, str) else None

            if code == 0x1B:
                try:
                    _SPK.end()
                except:
                    pass
                _LCD.fillScreen(_BLACK)
                return

            elif code == ord(' '):
                _paused = not _paused
                _draw_pause_indicator()
                if _paused:
                    try:
                        _SPK.tone(0, 1)
                    except:
                        pass
                else:
                    _note_start = time.ticks_ms()
                    if _note_idx < len(_notes) and _notes[_note_idx][0] > 0:
                        try:
                            _SPK.tone(_notes[_note_idx][0], _notes[_note_idx][1])
                        except:
                            pass

            elif code in (0xB7, ord('d'), ord('.')):
                _http_request(_PROXY + "/next", "POST")
                time.sleep_ms(500)
                _draw_chrome()
                _draw_loading()
                err = _fetch_synth_data()
                if err:
                    _draw_error(err)
                else:
                    _draw_chrome()
                    _draw_track_info()
                    _ripples = []
                    _note_idx = 0
                    _paused = False
                    _note_start = time.ticks_ms()
                    if _notes and _notes[0][0] > 0:
                        try:
                            _SPK.tone(_notes[0][0], _notes[0][1])
                        except:
                            pass
                        idx, name, octave = _freq_to_note(_notes[0][0])
                        if idx >= 0:
                            _spawn_ripple(idx)
                            _draw_note_name(idx, name, octave)
                    _draw_progress()

            elif code in (0xB4, ord('a'), ord(',')):
                _http_request(_PROXY + "/prev", "POST")
                time.sleep_ms(500)
                _draw_chrome()
                _draw_loading()
                err = _fetch_synth_data()
                if err:
                    _draw_error(err)
                else:
                    _draw_chrome()
                    _draw_track_info()
                    _ripples = []
                    _note_idx = 0
                    _paused = False
                    _note_start = time.ticks_ms()
                    if _notes and _notes[0][0] > 0:
                        try:
                            _SPK.tone(_notes[0][0], _notes[0][1])
                        except:
                            pass
                        idx, name, octave = _freq_to_note(_notes[0][0])
                        if idx >= 0:
                            _spawn_ripple(idx)
                            _draw_note_name(idx, name, octave)
                    _draw_progress()

        # Advance playback
        if not _paused and _notes and _note_idx < len(_notes):
            now = time.ticks_ms()
            dur = _notes[_note_idx][1]
            if time.ticks_diff(now, _note_start) >= dur:
                _note_idx += 1
                _note_start = now

                if _note_idx < len(_notes):
                    freq = _notes[_note_idx][0]
                    note_dur = _notes[_note_idx][1]
                    if freq > 0:
                        try:
                            _SPK.tone(freq, note_dur)
                        except:
                            pass
                        idx, name, octave = _freq_to_note(freq)
                        if idx >= 0:
                            _spawn_ripple(idx)
                            _draw_note_name(idx, name, octave)
                    else:
                        _clear_note_name()
                    _draw_progress()
                else:
                    # Finished — re-fetch (track may have changed)
                    _clear_note_name()
                    time.sleep_ms(1000)
                    _draw_loading()
                    err = _fetch_synth_data()
                    if err:
                        _draw_error(err)
                    else:
                        _draw_chrome()
                        _draw_track_info()
                        _ripples = []
                        _note_idx = 0
                        _note_start = time.ticks_ms()
                        if _notes and _notes[0][0] > 0:
                            try:
                                _SPK.tone(_notes[0][0], _notes[0][1])
                            except:
                                pass
                            idx, name, octave = _freq_to_note(_notes[0][0])
                            if idx >= 0:
                                _spawn_ripple(idx)
                                _draw_note_name(idx, name, octave)
                        _draw_progress()

        _draw_ripples()
        _tick += 1
        time.sleep_ms(40)
