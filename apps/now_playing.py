"""Now Playing — show the current Spotify track from the local proxy."""

import time
import json

import M5
from hardware import MatrixKeyboard

_LCD = M5.Lcd
_W = 240
_H = 135

_BLACK  = 0x000000
_DARK   = 0x1F1F1F
_GREEN  = 0x1DB954  # Spotify green
_WHITE  = 0xFFFFFF
_GRAY   = 0x777777
_DGRAY  = 0x444444

# Change this to your computer's local IP
_PROXY = "http://159.65.123.66:8888"
_POLL_INTERVAL = 3000  # ms between polls

_last_track = None


def _http_get(url):
    """Minimal HTTP GET using raw sockets (no urequests needed)."""
    import socket

    # Parse URL
    url = url.replace("http://", "")
    host_port, path = url.split("/", 1)
    path = "/" + path
    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 80

    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect((host, port))
        req = "GET {} HTTP/1.0\r\nHost: {}\r\n\r\n".format(path, host)
        s.send(req.encode())

        response = b""
        while True:
            try:
                chunk = s.recv(1024)
                if not chunk:
                    break
                response += chunk
            except:
                break

        # Split headers and body
        parts = response.split(b"\r\n\r\n", 1)
        if len(parts) == 2:
            return json.loads(parts[1])
        return None
    except:
        return None
    finally:
        s.close()


def _draw_chrome():
    _LCD.fillScreen(_BLACK)
    _LCD.fillRect(0, 0, _W, 17, _DARK)
    _LCD.fillRect(0, 17, _W, 1, _GREEN)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GREEN, _DARK)
    _LCD.drawString("Now Playing", 6, 4)

    _LCD.fillRect(0, _H - 17, _W, 17, _DARK)
    _LCD.setTextColor(_GRAY, _DARK)
    hint = "ESC: back"
    _LCD.drawString(hint, (_W - _LCD.textWidth(hint)) // 2, _H - 13)


def _draw_not_playing():
    _LCD.fillRect(0, 20, _W, _H - 37, _BLACK)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GRAY, _BLACK)
    msg = "Nothing playing"
    _LCD.drawString(msg, (_W - _LCD.textWidth(msg)) // 2, 65)


def _draw_error(msg):
    _LCD.fillRect(0, 20, _W, _H - 37, _BLACK)
    _LCD.setTextSize(1)
    _LCD.setTextColor(0xFF4444, _BLACK)
    _LCD.drawString(msg[:30], (_W - _LCD.textWidth(msg[:30])) // 2, 55)
    _LCD.setTextColor(_GRAY, _BLACK)
    hint = "Is the proxy running?"
    _LCD.drawString(hint, (_W - _LCD.textWidth(hint)) // 2, 75)


def _draw_track(track, artist, album, progress_ms, duration_ms):
    """Draw track info and progress bar."""
    global _last_track

    track_id = track + artist

    # Only redraw text if track changed
    if track_id != _last_track:
        _last_track = track_id

        # Clear content area
        _LCD.fillRect(0, 20, _W, _H - 37, _BLACK)

        # Track name (large)
        _LCD.setTextSize(2)
        _LCD.setTextColor(_WHITE, _BLACK)
        display_track = track[:16] if len(track) > 16 else track
        _LCD.drawString(display_track, 10, 28)

        # Artist
        _LCD.setTextSize(1)
        _LCD.setTextColor(_GREEN, _BLACK)
        display_artist = artist[:35] if len(artist) > 35 else artist
        _LCD.drawString(display_artist, 10, 55)

        # Album
        _LCD.setTextColor(_GRAY, _BLACK)
        display_album = album[:35] if len(album) > 35 else album
        _LCD.drawString(display_album, 10, 72)

    # Progress bar (always update)
    bar_y = 92
    bar_h = 6
    bar_w = _W - 20

    _LCD.fillRect(10, bar_y, bar_w, bar_h, _DGRAY)

    if duration_ms > 0:
        filled = (progress_ms * bar_w) // duration_ms
        if filled > 0:
            _LCD.fillRect(10, bar_y, filled, bar_h, _GREEN)

    # Time stamps
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GRAY, _BLACK)

    prog_s = progress_ms // 1000
    dur_s = duration_ms // 1000
    prog_str = "{}:{:02d}".format(prog_s // 60, prog_s % 60)
    dur_str = "{}:{:02d}".format(dur_s // 60, dur_s % 60)

    _LCD.fillRect(10, bar_y + 10, 50, 12, _BLACK)
    _LCD.drawString(prog_str, 10, bar_y + 10)
    _LCD.fillRect(_W - 45, bar_y + 10, 40, 12, _BLACK)
    _LCD.drawString(dur_str, _W - 10 - _LCD.textWidth(dur_str), bar_y + 10)


def run():
    global _last_track
    _last_track = None

    _draw_chrome()
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GRAY, _BLACK)
    msg = "Connecting to proxy..."
    _LCD.drawString(msg, (_W - _LCD.textWidth(msg)) // 2, 65)

    kb = MatrixKeyboard()
    time.sleep_ms(300)

    last_poll = 0

    while True:
        kb.tick()
        k = kb.get_key()

        if k is not None:
            code = k if isinstance(k, int) else ord(k) if isinstance(k, str) else None
            if code == 0x1B:
                _LCD.fillScreen(_BLACK)
                return

        now = time.ticks_ms()
        if time.ticks_diff(now, last_poll) >= _POLL_INTERVAL:
            last_poll = now

            data = _http_get(_PROXY + "/now-playing")

            if data is None:
                _draw_error("Can't reach proxy")
            elif data.get("error") == "not_authorized":
                _draw_error("Visit /login on proxy")
            elif not data.get("playing"):
                _draw_not_playing()
            else:
                _draw_track(
                    data.get("track", "?"),
                    data.get("artist", "?"),
                    data.get("album", ""),
                    data.get("progress_ms", 0),
                    data.get("duration_ms", 1),
                )

        time.sleep_ms(40)
