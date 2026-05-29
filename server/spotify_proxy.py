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
import tempfile

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


_PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.r4fo.com",
    "https://pipedapi.adminforge.de",
]


def _download_audio(track, artist):
    """Search Piped (YouTube frontend) and download audio to a temp file."""
    query = f"{track} {artist}"

    for base_url in _PIPED_INSTANCES:
        try:
            # Search for the track
            resp = requests.get(
                f"{base_url}/search",
                params={"q": query, "filter": "music_songs"},
                timeout=10,
            )
            if resp.status_code != 200:
                continue

            items = resp.json().get("items", [])
            if not items:
                # Try without filter
                resp = requests.get(
                    f"{base_url}/search",
                    params={"q": query, "filter": "videos"},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                items = resp.json().get("items", [])
                if not items:
                    continue

            # Get video ID from first result
            video_url = items[0].get("url", "")
            video_id = video_url.replace("/watch?v=", "")
            if not video_id:
                continue

            # Get audio streams
            resp = requests.get(
                f"{base_url}/streams/{video_id}", timeout=10,
            )
            if resp.status_code != 200:
                continue

            streams = resp.json().get("audioStreams", [])
            if not streams:
                continue

            # Pick the best bitrate audio stream
            stream = max(streams, key=lambda s: s.get("bitrate", 0))
            audio_url = stream["url"]

            # Download the audio
            resp = requests.get(audio_url, timeout=30, stream=True)
            if resp.status_code != 200:
                continue

            # Determine extension from mime type
            mime = stream.get("mimeType", "audio/webm")
            ext = "m4a" if "mp4" in mime else "webm"

            tmp_dir = tempfile.mkdtemp()
            audio_path = os.path.join(tmp_dir, f"audio.{ext}")
            with open(audio_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)

            app.logger.info(
                f"Downloaded from {base_url}: {video_id} ({ext})"
            )
            return audio_path, tmp_dir

        except Exception as e:
            app.logger.warning(f"Piped {base_url} failed: {e}")
            continue

    return None, None


def _extract_notes(audio_path):
    """Extract melody from an audio file using pitch detection."""
    import librosa
    import numpy as np

    y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=30)

    f0, _voiced, probs = librosa.pyin(
        y, fmin=130, fmax=1047, sr=sr,
        frame_length=2048, hop_length=1024,
    )

    hop_ms = (1024 / sr) * 1000  # ~46 ms per frame

    raw = []
    for i, freq in enumerate(f0):
        if np.isnan(freq) or freq < 100 or probs[i] < 0.3:
            raw.append([0, int(hop_ms)])
        else:
            midi = int(round(librosa.hz_to_midi(freq)))
            midi = max(60, min(84, midi))  # clamp C4-C6
            qfreq = int(round(librosa.midi_to_hz(midi)))
            raw.append([qfreq, int(hop_ms)])

    # Compress consecutive identical frequencies
    compressed = []
    for note in raw:
        if compressed and compressed[-1][0] == note[0]:
            compressed[-1][1] += note[1]
        else:
            compressed.append(list(note))

    # Drop entries shorter than 50 ms (absorb into previous)
    filtered = []
    for n in compressed:
        if n[1] >= 50:
            filtered.append(n)
        elif filtered:
            filtered[-1][1] += n[1]

    return filtered[:200]  # cap for ESP32 memory


@app.route("/synth-preview")
def synth_preview():
    import shutil

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

    # Return cached result if same track
    if _note_cache["track_id"] == track_id and _note_cache["notes"]:
        return jsonify({
            "ok": True,
            "track": track,
            "artist": artist,
            "notes": _note_cache["notes"],
        })

    # Download from YouTube and extract melody
    tmp_dir = None
    try:
        wav_path, tmp_dir = _download_audio(track, artist)
        if not wav_path:
            return jsonify({"ok": False, "error": "download_failed"})

        notes = _extract_notes(wav_path)
    except Exception as e:
        app.logger.error(f"Synth extraction failed: {e}")
        return jsonify({"ok": False, "error": "extraction_failed"})
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    if not notes:
        return jsonify({"ok": False, "error": "no_notes"})

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
