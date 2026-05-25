"""Now Playing — show the current Spotify track with controls."""

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

_PROXY = "https://riwashouse.live"
_POLL_INTERVAL = 3000  # ms between polls

_last_track = None

# Scroll state
_track_scroll = 0
_artist_scroll = 0
_track_text = ""
_artist_text = ""
_scroll_tick = 0
_SCROLL_SPEED = 3  # ticks per pixel shift
_SCROLL_PAD = 40   # pixels of gap before text repeats


def _http_request(url, method="GET"):
    """HTTP/HTTPS request using ssl-wrapped sockets."""
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
    s.settimeout(5)
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
                chunk = s.read(1024) if is_https else s.recv(1024)
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
    _LCD.fillRect(0, 17, _W, 1, _GREEN)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GREEN, _DARK)
    _LCD.drawString("Now Playing", 6, 4)

    _LCD.fillRect(0, _H - 17, _W, 17, _DARK)
    _LCD.setTextColor(_GRAY, _DARK)
    hint = "<prev  space:play/pause  >next  ESC"
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


def _scroll_text(text, y, color, text_size, scroll_offset):
    """Draw text with horizontal scrolling if it overflows."""
    _LCD.setTextSize(text_size)
    _LCD.setTextColor(color, _BLACK)
    tw = _LCD.textWidth(text)
    max_w = _W - 20  # 10px padding each side

    # Clear the line
    line_h = 16 if text_size == 2 else 10
    _LCD.fillRect(10, y, max_w, line_h, _BLACK)

    if tw <= max_w:
        # Fits — draw static
        _LCD.drawString(text, 10, y)
        return 0  # no scroll needed
    else:
        # Scrolling: draw at offset position
        # Use clip area to prevent overflow
        total_w = tw + _SCROLL_PAD
        offset = scroll_offset % total_w
        x = 10 - offset
        _LCD.drawString(text, x, y)
        # Draw repeat copy for seamless loop
        if x + tw < _W - 10:
            _LCD.drawString(text, x + tw + _SCROLL_PAD, y)
        return scroll_offset + 1


def _draw_track(track, artist, album, progress_ms, duration_ms):
    """Draw track info and progress bar."""
    global _last_track, _track_scroll, _artist_scroll
    global _track_text, _artist_text

    track_id = track + artist

    # Reset scroll on track change
    if track_id != _last_track:
        _last_track = track_id
        _track_scroll = 0
        _artist_scroll = 0
        _track_text = track
        _artist_text = artist

        # Clear content area
        _LCD.fillRect(0, 20, _W, _H - 37, _BLACK)

        # Album (static, doesn't scroll)
        _LCD.setTextSize(1)
        _LCD.setTextColor(_GRAY, _BLACK)
        display_album = album[:35] if len(album) > 35 else album
        _LCD.drawString(display_album, 10, 72)

    # Progress bar (always update)
    bar_y = 88
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


def _update_scroll():
    """Update scrolling text each frame."""
    global _scroll_tick, _track_scroll, _artist_scroll

    _scroll_tick += 1
    if _scroll_tick % _SCROLL_SPEED != 0:
        return

    if _track_text:
        _track_scroll = _scroll_text(_track_text, 28, _WHITE, 2, _track_scroll)
    if _artist_text:
        _artist_scroll = _scroll_text(_artist_text, 55, _GREEN, 1, _artist_scroll)


def run():
    global _last_track, _track_scroll, _artist_scroll, _scroll_tick
    global _track_text, _artist_text
    _last_track = None
    _track_scroll = 0
    _artist_scroll = 0
    _scroll_tick = 0
    _track_text = ""
    _artist_text = ""

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

            if code == 0x1B:  # ESC
                _LCD.fillScreen(_BLACK)
                return
            elif code == ord(' '):  # Space = play/pause
                _http_request(_PROXY + "/play-pause", "POST")
                last_poll = 0  # force refresh
            elif code in (0xB7, ord('d'), ord('.')):  # Right / d / . = next
                _http_request(_PROXY + "/next", "POST")
                _last_track = None  # force redraw
                time.sleep_ms(500)  # wait for Spotify to update
                last_poll = 0
            elif code in (0xB4, ord('a'), ord(',')):  # Left / a / , = prev
                _http_request(_PROXY + "/prev", "POST")
                _last_track = None
                time.sleep_ms(500)
                last_poll = 0

        now = time.ticks_ms()
        if time.ticks_diff(now, last_poll) >= _POLL_INTERVAL:
            last_poll = now

            data = _http_request(_PROXY + "/now-playing")

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

        _update_scroll()
        time.sleep_ms(40)
