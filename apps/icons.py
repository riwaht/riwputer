"""16x16 pixel-art icons stored as tuples of (row, col, color) triples.

Each icon is drawn at 2x scale (32x32 on screen) using fillRect calls.
Only non-background pixels are stored to save memory.
"""

# --- Synth icon: musical note (orange 0xCC785C) ---
ICON_SYNTH = (
    # Note head (filled oval at bottom-left)
    (10, 3), (10, 4), (10, 5), (10, 6),
    (11, 2), (11, 3), (11, 4), (11, 5), (11, 6), (11, 7),
    (12, 2), (12, 3), (12, 4), (12, 5), (12, 6), (12, 7),
    (13, 3), (13, 4), (13, 5), (13, 6),
    # Stem (vertical line going up)
    (3, 7), (4, 7), (5, 7), (6, 7), (7, 7), (8, 7), (9, 7), (10, 7),
    # Flag (two small lines at top-right)
    (3, 8), (3, 9), (3, 10),
    (4, 9), (4, 10), (4, 11),
    (5, 10), (5, 11), (5, 12),
    (6, 10), (6, 11),
    (7, 9), (7, 10),
)

# --- Wi-Fi icon: signal arcs (blue 0x3399FF) ---
ICON_WIFI = (
    # Dot at bottom center
    (13, 7), (13, 8), (14, 7), (14, 8),
    # First arc
    (10, 5), (10, 6), (10, 9), (10, 10),
    (11, 6), (11, 9),
    # Second arc
    (7, 3), (7, 4), (7, 11), (7, 12),
    (8, 4), (8, 5), (8, 10), (8, 11),
    (9, 5), (9, 10),
    # Third arc (outer)
    (4, 1), (4, 2), (4, 13), (4, 14),
    (5, 2), (5, 3), (5, 12), (5, 13),
    (6, 3), (6, 12),
)


# --- Now Playing icon: play triangle + sound waves (green 0x1DB954) ---
ICON_PLAY = (
    # Play triangle
    (4, 3), (4, 4),
    (5, 3), (5, 4), (5, 5),
    (6, 3), (6, 4), (6, 5), (6, 6),
    (7, 3), (7, 4), (7, 5), (7, 6), (7, 7),
    (8, 3), (8, 4), (8, 5), (8, 6), (8, 7),
    (9, 3), (9, 4), (9, 5), (9, 6),
    (10, 3), (10, 4), (10, 5),
    (11, 3), (11, 4),
    # Sound wave arcs
    (6, 9), (7, 9), (8, 9),
    (5, 11), (6, 11), (7, 11), (8, 11), (9, 11),
    (4, 13), (5, 13), (6, 13), (7, 13), (8, 13), (9, 13), (10, 13),
)


# --- Synth Player icon: beamed eighth notes (magenta 0xDD44DD) ---
ICON_SYNTHPLAY = (
    # Beam connecting the two notes
    (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (2, 10), (2, 11),
    # Left stem
    (3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3),
    # Right stem
    (3, 11), (4, 11), (5, 11), (6, 11), (7, 11), (8, 11),
    # Left note head
    (9, 2), (9, 3), (9, 4),
    (10, 1), (10, 2), (10, 3), (10, 4), (10, 5),
    (11, 1), (11, 2), (11, 3), (11, 4), (11, 5),
    (12, 2), (12, 3), (12, 4),
    # Right note head
    (9, 10), (9, 11), (9, 12),
    (10, 9), (10, 10), (10, 11), (10, 12), (10, 13),
    (11, 9), (11, 10), (11, 11), (11, 12), (11, 13),
    (12, 10), (12, 11), (12, 12),
)


def draw_icon(lcd, icon, x, y, color, scale=2):
    """Draw a 16x16 icon at position (x, y) with given scale."""
    for row, col in icon:
        lcd.fillRect(x + col * scale, y + row * scale, scale, scale, color)
