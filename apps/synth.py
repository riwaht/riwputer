"""Tiny synth — turn the Cardputer into a musical keyboard.

Each QWERTY row maps to a chromatic scale starting at C4.
Press keys to play notes. Visual ripples pulse on screen.
ESC exits back to UIFlow.
"""

import time
import math
import random

import M5
import machine
from hardware import MatrixKeyboard

_LCD = M5.Lcd
_SPK = M5.Speaker

_W = 240
_H = 135

# Colors
_BLACK   = 0x000000
_DARK    = 0x1F1F1F
_ORANGE  = 0xCC785C
_CREAM   = 0xF0EEE6
_GRAY    = 0x777777

# Note colors — each note gets a unique hue
_COLORS = [
    0xFF4444,  # C  red
    0xFF7744,  # C# orange-red
    0xFFAA33,  # D  orange
    0xFFDD22,  # D# yellow-orange
    0xEEEE00,  # E  yellow
    0x44DD44,  # F  green
    0x22CCAA,  # F# teal
    0x3399FF,  # G  blue
    0x6666FF,  # G# indigo
    0x9944FF,  # A  purple
    0xDD44DD,  # A# magenta
    0xFF4499,  # B  pink
]

# C4 chromatic scale frequencies
_FREQS = [
    262, 277, 294, 311, 330, 349,
    370, 392, 415, 440, 466, 494,
    523, 554, 587, 622, 659, 698,
    740, 784, 831, 880, 932, 988,
]

# Keyboard layout -> note index (two octaves across the keyboard)
# Bottom row: z x c v b n m = C4..B4
# Middle row: a s d f g h j k l = C5..Ab5
_KEYMAP = {
    ord('z'): 0,  ord('x'): 1,  ord('c'): 2,  ord('v'): 3,
    ord('b'): 4,  ord('n'): 5,  ord('m'): 6,
    ord('a'): 7,  ord('s'): 8,  ord('d'): 9,  ord('f'): 10,
    ord('g'): 11, ord('h'): 12, ord('j'): 13, ord('k'): 14,
    ord('l'): 15,
    ord('q'): 16, ord('w'): 17, ord('e'): 18, ord('r'): 19,
    ord('t'): 20, ord('y'): 21, ord('u'): 22, ord('i'): 23,
}

# Note names for display
_NAMES = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B",
] * 2

# Ripple state: list of (x, y, radius, color, birth_tick)
_ripples = []
_tick = 0


def _set_font():
    try:
        _LCD.setFont(_LCD.FONTS.DejaVu9)
    except:
        pass


def _draw_chrome():
    _LCD.fillScreen(_BLACK)
    _LCD.fillRect(0, 0, _W, 20, _DARK)
    _LCD.fillRect(0, 20, _W, 1, _ORANGE)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_ORANGE, _DARK)
    _LCD.drawString("Synth", 6, 5)

    # Key hints at bottom
    _LCD.fillRect(0, _H - 18, _W, 18, _DARK)
    _LCD.setTextColor(_GRAY, _DARK)
    hint = "Z-M  A-L  Q-I = notes   ESC quit"
    _LCD.drawString(hint, (_W - _LCD.textWidth(hint)) // 2, _H - 14)


def _spawn_ripple(note_idx):
    """Create a visual ripple at a position mapped to the note."""
    # Spread notes across the screen horizontally
    x = 10 + (note_idx * (_W - 20)) // 23
    y = 40 + random.randint(0, 50)
    color = _COLORS[note_idx % 12]
    _ripples.append([x, y, 3, color, _tick])


def _draw_ripples():
    """Animate expanding ripple circles, fading out."""
    global _ripples
    alive = []
    for r in _ripples:
        x, y, radius, color, birth = r
        age = _tick - birth
        if age > 15:
            # Erase the last ring
            _LCD.drawCircle(x, y, radius, _BLACK)
            continue
        # Erase previous ring
        if radius > 3:
            _LCD.drawCircle(x, y, radius - 2, _BLACK)
        radius = 3 + age * 3
        r[2] = radius
        # Clip to play area
        if y - radius > 20 and y + radius < _H - 18:
            _LCD.drawCircle(x, y, radius, color)
        alive.append(r)
    _ripples = alive


def _draw_note_name(note_idx):
    """Show the current note name big in the center."""
    name = _NAMES[note_idx]
    octave = "4" if note_idx < 12 else "5"
    text = name + octave
    color = _COLORS[note_idx % 12]

    # Clear center area
    _LCD.fillRect(80, 55, 80, 30, _BLACK)
    _LCD.setTextSize(2)
    _LCD.setTextColor(color, _BLACK)
    _LCD.drawString(text, (_W - _LCD.textWidth(text)) // 2, 58)


def _play_note(note_idx):
    freq = _FREQS[note_idx]
    try:
        _SPK.tone(freq, 150)
    except:
        pass


def run():
    global _tick

    _set_font()

    try:
        _SPK.begin()
        _SPK.setVolume(80)
    except:
        pass

    _draw_chrome()

    # Draw resting state label
    _LCD.setTextSize(1)
    _LCD.setTextColor(_GRAY, _BLACK)
    msg = "press a key to play"
    _LCD.drawString(msg, (_W - _LCD.textWidth(msg)) // 2, 70)

    kb = MatrixKeyboard()
    time.sleep_ms(400)

    try:
        while True:
            kb.tick()
            k = kb.get_key()

            if k is not None:
                # ESC to exit
                if isinstance(k, int) and k == 0x1B:
                    return

                code = k if isinstance(k, int) else ord(k) if isinstance(k, str) else None
                if code and code in _KEYMAP:
                    idx = _KEYMAP[code]
                    _play_note(idx)
                    _spawn_ripple(idx)
                    _draw_note_name(idx)

            _draw_ripples()
            _tick += 1
            time.sleep_ms(40)
    finally:
        try:
            _SPK.end()
        except:
            pass
        try:
            _LCD.fillScreen(_BLACK)
        except:
            pass
        time.sleep_ms(200)
