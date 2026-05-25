"""Riwriw — pixel-art launcher for the M5Stack Cardputer."""

import time
import json
import network

import M5
from hardware import MatrixKeyboard

from apps.icons import ICON_SYNTH, ICON_WIFI, ICON_PLAY, draw_icon

_LCD = M5.Lcd

_W = 240
_H = 135

# Colors
_BLACK  = 0x000000
_DARK   = 0x1F1F1F
_WHITE  = 0xFFFFFF
_GRAY   = 0x777777
_ORANGE = 0xCC785C
_BLUE   = 0x3399FF

# Grid layout
_COLS = 4
_ROWS = 2
_GRID_TOP = 18
_GRID_BOT = _H - 18
_GRID_H = _GRID_BOT - _GRID_TOP
_CELL_W = _W // _COLS        # 60
_CELL_H = _GRID_H // _ROWS   # ~49

# App registry
APPS = [
    {"name": "Synth",  "icon": ICON_SYNTH, "color": _ORANGE, "module": "apps.synth"},
    {"name": "Wi-Fi",  "icon": ICON_WIFI,  "color": _BLUE,   "module": "apps.wifi_scanner"},
    {"name": "Playing", "icon": ICON_PLAY, "color": 0x1DB954, "module": "apps.now_playing"},
]

# Selection state
_sel = 0
_pulse_tick = 0


def _wifi_connected():
    """Check if Wi-Fi station is connected."""
    try:
        sta = network.WLAN(network.STA_IF)
        return sta.isconnected()
    except:
        return False


def _draw_status_bar():
    """Draw top status bar with branding and Wi-Fi indicator."""
    _LCD.fillRect(0, 0, _W, 17, _DARK)

    _LCD.setTextSize(1)
    _LCD.setTextColor(_ORANGE, _DARK)
    _LCD.drawString("Riwriw", 6, 4)

    # Wi-Fi indicator on the right
    wx = _W - 30
    wy = 4
    if _wifi_connected():
        _LCD.setTextColor(_BLUE, _DARK)
        _LCD.drawString("WiFi", wx, wy)
    else:
        _LCD.setTextColor(_GRAY, _DARK)
        _LCD.drawString("----", wx, wy)


def _draw_footer():
    """Draw bottom footer with key hints."""
    _LCD.fillRect(0, _H - 17, _W, 17, _DARK)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GRAY, _DARK)
    hint = "ENTER: launch   arrows: move"
    _LCD.drawString(hint, (_W - _LCD.textWidth(hint)) // 2, _H - 13)


def _cell_xy(idx):
    """Get top-left pixel coords for a grid cell index."""
    col = idx % _COLS
    row = idx // _COLS
    x = col * _CELL_W
    y = _GRID_TOP + row * _CELL_H
    return x, y


def _draw_app_cell(idx, selected):
    """Draw a single app cell."""
    if idx >= len(APPS):
        return

    app = APPS[idx]
    x, y = _cell_xy(idx)

    # Clear cell
    _LCD.fillRect(x + 1, y + 1, _CELL_W - 2, _CELL_H - 2, _BLACK)

    # Draw icon centered in cell (icon is 32x32 at 2x scale)
    icon_x = x + (_CELL_W - 32) // 2
    icon_y = y + 4
    draw_icon(_LCD, app["icon"], icon_x, icon_y, app["color"])

    # Draw name below icon
    _LCD.setTextSize(1)
    _LCD.setTextColor(app["color"] if selected else _GRAY, _BLACK)
    name_x = x + (_CELL_W - _LCD.textWidth(app["name"])) // 2
    _LCD.drawString(app["name"], name_x, y + 38)

    # Selection border
    if selected:
        _LCD.drawRect(x, y, _CELL_W, _CELL_H, app["color"])
    else:
        # Clear any old border
        _LCD.drawRect(x, y, _CELL_W, _CELL_H, _BLACK)


def _draw_grid():
    """Draw the full app grid."""
    for i in range(_COLS * _ROWS):
        _draw_app_cell(i, i == _sel)


def _pulse_selection():
    """Animate the selection border with a pulse."""
    global _pulse_tick
    _pulse_tick += 1

    if _sel >= len(APPS):
        return

    app = APPS[_sel]
    x, y = _cell_xy(_sel)

    # Alternate between app color and dimmed version
    if (_pulse_tick // 6) % 2 == 0:
        color = app["color"]
    else:
        # Dim: halve each channel
        r = ((app["color"] >> 16) & 0xFF) // 2
        g = ((app["color"] >> 8) & 0xFF) // 2
        b = (app["color"] & 0xFF) // 2
        color = (r << 16) | (g << 8) | b

    _LCD.drawRect(x, y, _CELL_W, _CELL_H, color)


def _launch_app(idx):
    """Import and run the selected app."""
    if idx >= len(APPS):
        return

    mod_name = APPS[idx]["module"]
    try:
        mod = __import__(mod_name)
        # Handle dotted module names (apps.synth -> need apps then synth)
        for part in mod_name.split(".")[1:]:
            mod = getattr(mod, part)
        mod.run()
    except Exception as e:
        _LCD.fillScreen(_BLACK)
        _LCD.setTextSize(1)
        _LCD.setTextColor(0xFF4444, _BLACK)
        _LCD.drawString("Error:", 10, 50)
        _LCD.drawString(str(e)[:30], 10, 65)
        time.sleep_ms(2000)


def _auto_connect_wifi():
    """Try to connect using saved credentials."""
    try:
        with open("/flash/wifi_creds.json", "r") as f:
            creds = json.load(f)
        ssid = creds.get("ssid")
        pw = creds.get("password", "")
        if not ssid:
            return
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if sta.isconnected():
            return
        sta.connect(ssid, pw)
        for _ in range(15):
            if sta.isconnected():
                return
            time.sleep_ms(500)
    except:
        pass


def run():
    global _sel

    _LCD.fillScreen(_BLACK)

    # Show boot splash while connecting
    _LCD.setTextSize(1)
    _LCD.setTextColor(_ORANGE, _BLACK)
    _LCD.drawString("Riwriw", 100, 60)
    _LCD.setTextColor(_GRAY, _BLACK)
    _LCD.drawString("connecting...", 88, 78)
    _auto_connect_wifi()

    _LCD.fillScreen(_BLACK)
    _draw_status_bar()
    _draw_footer()
    _draw_grid()

    kb = MatrixKeyboard()
    time.sleep_ms(300)

    while True:
        kb.tick()
        k = kb.get_key()

        if k is not None:
            code = k if isinstance(k, int) else ord(k) if isinstance(k, str) else None
            old_sel = _sel
            max_idx = len(APPS) - 1

            if code == 0x1B:
                # ESC — do nothing at launcher level
                pass
            elif code in (0xB4, ord('a')):  # Left arrow or 'a'
                _sel = max(0, _sel - 1)
            elif code in (0xB7, ord('d')):  # Right arrow or 'd'
                _sel = min(max_idx, _sel + 1)
            elif code in (0xB5, ord('w')):  # Up arrow or 'w'
                if _sel >= _COLS:
                    _sel -= _COLS
            elif code in (0xB6, ord('s')):  # Down arrow or 's'
                if _sel + _COLS <= max_idx:
                    _sel += _COLS
            elif code in (0x0D, 0x0A, ord('\r'), ord('\n')):  # Enter
                _launch_app(_sel)
                # Redraw everything after app returns
                _LCD.fillScreen(_BLACK)
                _draw_status_bar()
                _draw_footer()
                _draw_grid()
                time.sleep_ms(300)
                continue

            if old_sel != _sel:
                _draw_app_cell(old_sel, False)
                _draw_app_cell(_sel, True)

        _pulse_selection()
        time.sleep_ms(40)
