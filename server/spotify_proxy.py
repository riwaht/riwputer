"""Spotify Now Playing proxy for the Cardputer.

Run this on your computer. It handles Spotify OAuth and serves a simple
JSON endpoint the Cardputer can poll over local Wi-Fi.

Usage:
    pip install flask requests python-dotenv
    python spotify_proxy.py

Then visit http://127.0.0.1:8888/login to authorize with Spotify.
The Cardputer hits http://<your-ip>:8888/now-playing for track info.
"""

import os
import time
import threading
import hashlib
import struct

from flask import Flask, redirect, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REDIRECT_URI = "https://riwashouse.live/callback"
SCOPE = "user-read-currently-playing user-read-playback-state user-modify-playback-state"

app = Flask(__name__)

# Note cache for synth preview
_note_cache = {"track_id": None, "notes": [], "track": "", "artist": ""}

# Token state
_token = {
    "access_token": None,
    "refresh_token": None,
    "expires_at": 0,
}
_lock = threading.Lock()


def _refresh_if_needed():
    """Refresh the access token if it's expired."""
    with _lock:
        if _token["access_token"] and time.time() < _token["expires_at"] - 60:
            return _token["access_token"]

        if not _token["refresh_token"]:
            return None

        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": _token["refresh_token"],
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        _token["access_token"] = data["access_token"]
        _token["expires_at"] = time.time() + data["expires_in"]
        if "refresh_token" in data:
            _token["refresh_token"] = data["refresh_token"]

        return _token["access_token"]


@app.route("/login")
def login():
    url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPE}"
    )
    return redirect(url)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "No code received", 400

    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    if resp.status_code != 200:
        return f"Token exchange failed: {resp.text}", 400

    data = resp.json()
    with _lock:
        _token["access_token"] = data["access_token"]
        _token["refresh_token"] = data["refresh_token"]
        _token["expires_at"] = time.time() + data["expires_in"]

    return "Authorized! Your Cardputer can now show what's playing. You can close this tab."


@app.route("/now-playing")
def now_playing():
    token = _refresh_if_needed()
    if not token:
        return jsonify({"playing": False, "error": "not_authorized"}), 401

    resp = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={"Authorization": f"Bearer {token}"},
    )

    if resp.status_code == 204 or resp.status_code == 202:
        return jsonify({"playing": False})

    if resp.status_code != 200:
        return jsonify({"playing": False, "error": resp.status_code})

    data = resp.json()
    if not data.get("is_playing"):
        return jsonify({"playing": False})

    item = data.get("item", {})
    return jsonify({
        "playing": True,
        "track": item.get("name", "Unknown"),
        "artist": ", ".join(a["name"] for a in item.get("artists", [])),
        "album": item.get("album", {}).get("name", ""),
        "progress_ms": data.get("progress_ms", 0),
        "duration_ms": item.get("duration_ms", 1),
    })


@app.route("/play-pause", methods=["POST"])
def play_pause():
    token = _refresh_if_needed()
    if not token:
        return jsonify({"ok": False, "error": "not_authorized"}), 401

    headers = {"Authorization": f"Bearer {token}"}

    # Check current state
    resp = requests.get(
        "https://api.spotify.com/v1/me/player",
        headers=headers,
    )
    if resp.status_code != 200:
        return jsonify({"ok": False})

    is_playing = resp.json().get("is_playing", False)

    if is_playing:
        requests.put("https://api.spotify.com/v1/me/player/pause", headers=headers)
    else:
        requests.put("https://api.spotify.com/v1/me/player/play", headers=headers)

    return jsonify({"ok": True})


@app.route("/next", methods=["POST"])
def next_track():
    token = _refresh_if_needed()
    if not token:
        return jsonify({"ok": False, "error": "not_authorized"}), 401

    requests.post(
        "https://api.spotify.com/v1/me/player/next",
        headers={"Authorization": f"Bearer {token}"},
    )
    return jsonify({"ok": True})


@app.route("/prev", methods=["POST"])
def prev_track():
    token = _refresh_if_needed()
    if not token:
        return jsonify({"ok": False, "error": "not_authorized"}), 401

    requests.post(
        "https://api.spotify.com/v1/me/player/previous",
        headers={"Authorization": f"Bearer {token}"},
    )
    return jsonify({"ok": True})


# Pentatonic scales — sound good on a tiny speaker.
# Each scale is semitone offsets from the root, spanning two octaves.
_MAJOR_PENTA = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21]   # happy
_MINOR_PENTA = [0, 3, 5, 7, 10, 12, 15, 17, 19, 22]   # moody


def _seeded_rng(seed_bytes):
    """Simple deterministic PRNG from a seed.  Returns a callable that
    produces ints in a given range — same seed always gives the same
    sequence."""
    state = list(struct.unpack(">4I", seed_bytes[:16]))

    def _next(lo, hi):
        # xoshiro128** core
        r = ((state[1] * 5) & 0xFFFFFFFF)
        r = (((r << 7) | (r >> 25)) * 9) & 0xFFFFFFFF
        t = (state[1] << 9) & 0xFFFFFFFF
        state[2] ^= state[0]
        state[3] ^= state[1]
        state[1] ^= state[2]
        state[0] ^= state[3]
        state[2] ^= t
        state[3] = ((state[3] << 11) | (state[3] >> 21)) & 0xFFFFFFFF
        return lo + (r % (hi - lo + 1))

    return _next


def _generate_melody(track_id, duration_ms):
    """Generate a deterministic melody from a track ID.

    The track ID is hashed to seed a PRNG that picks a root note, scale,
    tempo, and note pattern.  The same track always produces the same
    melody.
    """
    seed = hashlib.md5(track_id.encode()).digest()
    rng = _seeded_rng(seed)

    # Pick root note (C4=60 through B4=71)
    root_midi = 60 + (seed[0] % 12)

    # Pick scale — use the second seed byte
    scale = _MINOR_PENTA if seed[1] % 2 == 0 else _MAJOR_PENTA

    # Tempo: note duration range 120-400 ms
    base_dur = 120 + (seed[2] % 280)

    # Build note sequence to fill the track duration
    notes = []
    total_ms = 0
    prev_scale_idx = len(scale) // 2  # start mid-scale

    while total_ms < duration_ms and len(notes) < 200:
        # Weighted random walk: prefer stepwise motion
        step = rng(-2, 2)
        new_idx = max(0, min(len(scale) - 1, prev_scale_idx + step))
        prev_scale_idx = new_idx

        midi = root_midi + scale[new_idx]
        midi = max(60, min(84, midi))
        freq = round(440 * 2 ** ((midi - 69) / 12))

        # Vary note duration slightly
        dur = base_dur + rng(-40, 40)

        # Occasionally add a rest (~15% chance)
        if rng(0, 99) < 15:
            rest_dur = rng(80, 200)
            notes.append([0, rest_dur])
            total_ms += rest_dur

        notes.append([freq, dur])
        total_ms += dur

    return notes


@app.route("/synth-preview")
def synth_preview():
    token = _refresh_if_needed()
    if not token:
        return jsonify({"ok": False, "error": "not_authorized"}), 401

    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers=headers,
    )

    if resp.status_code == 204 or resp.status_code == 202:
        return jsonify({"ok": False, "error": "not_playing"})
    if resp.status_code != 200:
        return jsonify({"ok": False, "error": "api_error"})

    data = resp.json()
    item = data.get("item", {})
    track_id = item.get("id", "")
    track = item.get("name", "Unknown")
    artist = ", ".join(a["name"] for a in item.get("artists", []))
    duration_ms = item.get("duration_ms", 30000)

    # Return cached result if same track
    if _note_cache["track_id"] == track_id and _note_cache["notes"]:
        return jsonify({
            "ok": True,
            "track": track,
            "artist": artist,
            "notes": _note_cache["notes"],
        })

    notes = _generate_melody(track_id, duration_ms)

    _note_cache["track_id"] = track_id
    _note_cache["notes"] = notes
    _note_cache["track"] = track
    _note_cache["artist"] = artist

    return jsonify({
        "ok": True,
        "track": track,
        "artist": artist,
        "notes": notes,
    })


if __name__ == "__main__":
    print("Spotify proxy starting on http://127.0.0.1:8888")
    print("Step 1: Visit http://127.0.0.1:8888/login to authorize")
    print("Step 2: The Cardputer will poll /now-playing automatically")
    app.run(host="0.0.0.0", port=8888)
