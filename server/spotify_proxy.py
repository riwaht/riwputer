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

from flask import Flask, redirect, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REDIRECT_URI = "http://159.65.123.66:8888/callback"
SCOPE = "user-read-currently-playing user-read-playback-state"

app = Flask(__name__)

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


if __name__ == "__main__":
    print("Spotify proxy starting on http://127.0.0.1:8888")
    print("Step 1: Visit http://127.0.0.1:8888/login to authorize")
    print("Step 2: The Cardputer will poll /now-playing automatically")
    app.run(host="0.0.0.0", port=8888)
