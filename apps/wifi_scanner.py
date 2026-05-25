"""Wi-Fi Connect — scan, pick, type password, connect, save credentials."""

import time
import json
import network

import M5
from hardware import MatrixKeyboard

_LCD = M5.Lcd
_W = 240
_H = 135

_BLACK  = 0x000000
_DARK   = 0x1F1F1F
_BLUE   = 0x3399FF
_GRAY   = 0x777777
_GREEN  = 0x44DD44
_RED    = 0xFF4444
_WHITE  = 0xFFFFFF
_ORANGE = 0xCC785C

_CREDS_PATH = "/flash/wifi_creds.json"

# Scan results and selection state
_networks = []
_sel = 0
_scroll_offset = 0
_MAX_VISIBLE = 5  # rows visible in the list


def _draw_chrome(title):
    _LCD.fillScreen(_BLACK)
    _LCD.fillRect(0, 0, _W, 17, _DARK)
    _LCD.fillRect(0, 17, _W, 1, _BLUE)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_BLUE, _DARK)
    _LCD.drawString(title, 6, 4)

    _LCD.fillRect(0, _H - 17, _W, 17, _DARK)
    _LCD.setTextColor(_GRAY, _DARK)


def _draw_footer(text):
    _LCD.fillRect(0, _H - 17, _W, 17, _DARK)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GRAY, _DARK)
    _LCD.drawString(text, (_W - _LCD.textWidth(text)) // 2, _H - 13)


def _signal_bars(rssi):
    """Convert RSSI to 0-4 bar rating."""
    if rssi >= -50:
        return 4
    elif rssi >= -60:
        return 3
    elif rssi >= -70:
        return 2
    elif rssi >= -80:
        return 1
    return 0


def _draw_network_list():
    """Draw the list of scanned networks."""
    list_top = 22
    row_h = 18

    # Clear list area
    _LCD.fillRect(0, list_top, _W, _MAX_VISIBLE * row_h, _BLACK)

    for i in range(_MAX_VISIBLE):
        idx = _scroll_offset + i
        if idx >= len(_networks):
            break

        ssid, rssi, auth = _networks[idx]
        y = list_top + i * row_h
        selected = (idx == _sel)

        # Highlight bar
        if selected:
            _LCD.fillRect(0, y, _W, row_h - 1, _DARK)

        # SSID
        _LCD.setTextSize(1)
        color = _WHITE if selected else _GRAY
        _LCD.setTextColor(color, _DARK if selected else _BLACK)

        display_ssid = ssid[:20] if len(ssid) > 20 else ssid
        _LCD.drawString(display_ssid, 6, y + 4)

        # Signal bars
        bars = _signal_bars(rssi)
        bx = _W - 40
        for b in range(4):
            bar_h = 3 + b * 3
            bar_color = _BLUE if b < bars else 0x333333
            _LCD.fillRect(bx + b * 6, y + 14 - bar_h, 4, bar_h, bar_color)

        # Lock icon (if encrypted)
        if auth > 0:
            _LCD.setTextColor(_ORANGE, _DARK if selected else _BLACK)
            _LCD.drawString("*", _W - 50, y + 4)

    # Scroll indicator
    if len(_networks) > _MAX_VISIBLE:
        _LCD.setTextSize(1)
        _LCD.setTextColor(_GRAY, _BLACK)
        indicator = "{}/{}".format(_sel + 1, len(_networks))
        _LCD.drawString(indicator, _W - 35, list_top + _MAX_VISIBLE * row_h + 2)


def _scan_networks():
    """Scan for Wi-Fi networks and sort by signal strength."""
    global _networks, _sel, _scroll_offset

    _draw_chrome("Wi-Fi")
    _LCD.setTextSize(1)
    _LCD.setTextColor(_BLUE, _BLACK)
    msg = "Scanning..."
    _LCD.drawString(msg, (_W - _LCD.textWidth(msg)) // 2, 60)

    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    time.sleep_ms(200)

    raw = sta.scan()

    # Deduplicate by SSID, keep strongest signal
    seen = {}
    for entry in raw:
        ssid = entry[0].decode("utf-8", "replace")
        rssi = entry[3]
        auth = entry[4]
        if ssid and (ssid not in seen or rssi > seen[ssid][1]):
            seen[ssid] = (ssid, rssi, auth)

    _networks = sorted(seen.values(), key=lambda x: x[1], reverse=True)
    _sel = 0
    _scroll_offset = 0


def _get_password(ssid):
    """Show a password input screen. Returns password string or None on ESC."""
    _draw_chrome("Password for " + ssid[:15])
    _draw_footer("Type password, ENTER to connect")

    password = ""
    cursor_tick = 0

    kb = MatrixKeyboard()
    time.sleep_ms(200)

    while True:
        kb.tick()
        k = kb.get_key()

        if k is not None:
            code = k if isinstance(k, int) else ord(k) if isinstance(k, str) else None

            if code == 0x1B:  # ESC
                return None
            elif code in (0x0D, 0x0A):  # Enter
                return password
            elif code == 0x08 or code == 0x7F:  # Backspace/Delete
                if password:
                    password = password[:-1]
            elif code and 0x20 <= code <= 0x7E:  # Printable ASCII
                if len(password) < 64:
                    password += chr(code)

        # Draw password field
        cursor_tick += 1
        _LCD.fillRect(10, 50, _W - 20, 20, _DARK)
        _LCD.setTextSize(1)
        _LCD.setTextColor(_WHITE, _DARK)

        # Show last 25 chars with dots for earlier ones
        display = password[-25:] if len(password) > 25 else password
        # Show cursor
        cursor = "_" if (cursor_tick // 8) % 2 == 0 else " "
        _LCD.drawString(display + cursor, 14, 56)

        # Show length
        _LCD.setTextColor(_GRAY, _BLACK)
        _LCD.drawString("{}/64".format(len(password)), _W - 35, 75)

        time.sleep_ms(40)


def _connect(ssid, password):
    """Attempt to connect to the network. Returns True on success."""
    _draw_chrome("Connecting...")
    _LCD.setTextSize(1)
    _LCD.setTextColor(_BLUE, _BLACK)
    _LCD.drawString(ssid, (_W - _LCD.textWidth(ssid)) // 2, 50)

    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    # Disconnect if already connected
    if sta.isconnected():
        sta.disconnect()
        time.sleep_ms(500)

    sta.connect(ssid, password)

    # Wait up to 10 seconds
    for i in range(20):
        if sta.isconnected():
            break
        # Progress dots
        _LCD.setTextColor(_GRAY, _BLACK)
        _LCD.drawString("." * (i + 1), 10, 70)
        time.sleep_ms(500)

    if sta.isconnected():
        ip = sta.ifconfig()[0]

        # Save credentials
        try:
            with open(_CREDS_PATH, "w") as f:
                json.dump({"ssid": ssid, "password": password}, f)
        except:
            pass

        _draw_chrome("Connected!")
        _LCD.setTextSize(1)
        _LCD.setTextColor(_GREEN, _BLACK)
        _LCD.drawString(ssid, (_W - _LCD.textWidth(ssid)) // 2, 45)
        _LCD.setTextColor(_WHITE, _BLACK)
        _LCD.drawString("IP: " + ip, (_W - _LCD.textWidth("IP: " + ip)) // 2, 65)
        _draw_footer("Press any key")

        kb = MatrixKeyboard()
        time.sleep_ms(300)
        while True:
            kb.tick()
            if kb.get_key() is not None:
                return True
            time.sleep_ms(40)
    else:
        _draw_chrome("Failed")
        _LCD.setTextSize(1)
        _LCD.setTextColor(_RED, _BLACK)
        msg = "Could not connect"
        _LCD.drawString(msg, (_W - _LCD.textWidth(msg)) // 2, 55)
        _draw_footer("Press any key")

        kb = MatrixKeyboard()
        time.sleep_ms(300)
        while True:
            kb.tick()
            if kb.get_key() is not None:
                return False
            time.sleep_ms(40)


def run():
    global _sel, _scroll_offset

    _scan_networks()

    _draw_chrome("Wi-Fi")
    _draw_footer("ENTER: connect  R: rescan  ESC: back")
    _draw_network_list()

    kb = MatrixKeyboard()
    time.sleep_ms(300)

    while True:
        kb.tick()
        k = kb.get_key()

        if k is not None:
            code = k if isinstance(k, int) else ord(k) if isinstance(k, str) else None

            if code == 0x1B:  # ESC
                _LCD.fillScreen(_BLACK)
                return

            elif code in (0xB5, ord('w')):  # Up
                if _sel > 0:
                    _sel -= 1
                    if _sel < _scroll_offset:
                        _scroll_offset = _sel
                    _draw_network_list()

            elif code in (0xB6, ord('s')):  # Down
                if _sel < len(_networks) - 1:
                    _sel += 1
                    if _sel >= _scroll_offset + _MAX_VISIBLE:
                        _scroll_offset = _sel - _MAX_VISIBLE + 1
                    _draw_network_list()

            elif code in (0x0D, 0x0A) and _networks:  # Enter
                ssid, rssi, auth = _networks[_sel]
                if auth > 0:
                    pw = _get_password(ssid)
                    if pw is not None:
                        if _connect(ssid, pw):
                            _LCD.fillScreen(_BLACK)
                            return
                else:
                    # Open network
                    if _connect(ssid, ""):
                        _LCD.fillScreen(_BLACK)
                        return

                # Back to list after failed connect or cancelled password
                _draw_chrome("Wi-Fi")
                _draw_footer("ENTER: connect  R: rescan  ESC: back")
                _draw_network_list()

            elif code == ord('r') or code == ord('R'):  # Rescan
                _scan_networks()
                _draw_chrome("Wi-Fi")
                _draw_footer("ENTER: connect  R: rescan  ESC: back")
                _draw_network_list()

        time.sleep_ms(40)
