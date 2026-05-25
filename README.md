# riwputer

Apps and experiments for the M5Stack Cardputer, powered by the Riwriw launcher.

## Riwriw Launcher

A pixel-art home screen with a grid of app icons, status bar (Wi-Fi indicator), and key hints. Boots automatically on startup.

- **Arrow keys**: Navigate the grid
- **Enter**: Launch app
- **ESC**: Return to launcher from any app

## Apps

### Synth

A tiny synthesizer that turns the Cardputer into a musical keyboard. Two octaves mapped across the QWERTY rows with colorful ripple visuals.

- **Bottom row** (Z–M): C4 to G4
- **Middle row** (A–L): G#4 to D#5
- **Top row** (Q–I): E5 to B5

### Wi-Fi Connect

Scan for nearby networks, pick one, type the password, and connect. Credentials are saved on the device for auto-connect on boot.

- **Up/Down**: Browse networks
- **Enter**: Connect
- **R**: Rescan

### Now Playing (Spotify)

Shows the currently playing Spotify track with artist, album, and a progress bar. Requires the Spotify proxy server running on a machine or server.

#### Setup

1. Create a Spotify app at https://developer.spotify.com/dashboard
2. Set redirect URI to `http://<your-server-ip>:8888/callback`
3. Copy `.env.example` to `server/.env` and fill in your credentials
4. Install dependencies: `pip install -r server/requirements.txt`
5. Run the proxy: `python server/spotify_proxy.py`
6. Authorize at `http://<your-server-ip>:8888/login`
7. Update `_PROXY` in `apps/now_playing.py` to point to your server
