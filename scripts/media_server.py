#!/usr/bin/env python3
"""
AniHermes LAN Media Server
Serves the anime library over HTTP with a styled browse UI and video player.
Supports HTTP Range requests for seeking, concurrent clients via threading.
Built-in video player with subtitle support (.srt/.ass/.vtt converted on-the-fly).
No external dependencies — stdlib only.
"""

import argparse
import html
import json as _json
import mimetypes
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

FFPROBE = shutil.which("ffprobe")
FFMPEG = shutil.which("ffmpeg")

# Add scripts dir to path for config import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config

PID_FILE = os.path.expanduser("~/.hermes/anihermes/server.pid")

# Extra MIME types for anime files
EXTRA_MIMES = {
    ".mkv": "video/x-matroska",
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".ass": "text/plain",
    ".srt": "text/plain",
    ".vtt": "text/vtt",
    ".nfo": "text/plain",
}

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".webm"}
SUB_EXTS = {".srt", ".ass", ".ssa", ".vtt"}

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 1rem; }
a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 1.4rem; margin-bottom: 1rem; border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; }
.breadcrumb { font-size: 0.9rem; margin-bottom: 1rem; color: #8b949e; }
.breadcrumb a { color: #8b949e; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem; transition: border-color 0.2s; }
.card:hover { border-color: #58a6ff; }
.card .title { font-weight: 600; margin-bottom: 0.3rem; word-break: break-word; }
.card .meta { font-size: 0.8rem; color: #8b949e; }
.list { list-style: none; }
.list li { padding: 0.6rem 0; border-bottom: 1px solid #21262d; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.list li:last-child { border-bottom: none; }
.list .size { color: #8b949e; font-size: 0.85rem; }
.list .subs { font-size: 0.75rem; color: #3fb950; }
.back { display: inline-block; margin-bottom: 1rem; }
.btn { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.8rem; }
.btn-play { background: #238636; color: #fff; }
.btn-play:hover { background: #2ea043; text-decoration: none; }
.btn-dl { background: #30363d; color: #8b949e; }
.btn-dl:hover { background: #3d444d; text-decoration: none; }
@media (max-width: 600px) { .grid { grid-template-columns: 1fr 1fr; } }
"""

PLAYER_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #000; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.player-wrap { width: 100vw; height: 100vh; display: flex; flex-direction: column; }
video { flex: 1; width: 100%; background: #000; }
.controls { background: #161b22; padding: 0.6rem 1rem; display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.controls a { color: #58a6ff; text-decoration: none; font-size: 0.9rem; }
.controls .title { color: #e6edf3; font-size: 0.9rem; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.controls .sub-selector { font-size: 0.85rem; }
.controls select { background: #21262d; color: #e6edf3; border: 1px solid #30363d; border-radius: 4px; padding: 0.2rem 0.4rem; font-size: 0.85rem; }
.controls .btn { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.8rem; }
.controls .btn-dl { background: #30363d; color: #8b949e; }
.nav-buttons { display: flex; gap: 0.5rem; }
.nav-buttons a { padding: 0.25rem 0.6rem; border-radius: 4px; background: #30363d; color: #e6edf3; font-size: 0.85rem; }
.nav-buttons a:hover { background: #3d444d; text-decoration: none; }
"""


# ── Subtitle conversion ──────────────────────────────────────────────


def _srt_to_vtt(srt_text):
    """Convert SRT subtitle text to WebVTT."""
    vtt = "WEBVTT\n\n"
    # Normalize line endings
    srt_text = srt_text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace comma with dot in timestamps (00:01:23,456 → 00:01:23.456)
    srt_text = re.sub(
        r"(\d{2}:\d{2}:\d{2}),(\d{3})",
        r"\1.\2",
        srt_text,
    )
    # Remove sequence numbers (lines that are just digits before timestamps)
    blocks = re.split(r"\n\n+", srt_text.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue
        # Skip the sequence number line
        if lines[0].strip().isdigit():
            lines = lines[1:]
        if lines:
            vtt += "\n".join(lines) + "\n\n"
    return vtt


def _ass_to_vtt(ass_text):
    """Convert ASS/SSA subtitle text to WebVTT (basic conversion)."""
    vtt = "WEBVTT\n\n"
    # Normalize line endings
    ass_text = ass_text.replace("\r\n", "\n").replace("\r", "\n")

    in_events = False
    format_fields = []

    for line in ass_text.split("\n"):
        stripped = line.strip()

        if stripped.lower() == "[events]":
            in_events = True
            continue
        if stripped.startswith("[") and in_events:
            break  # New section, done with events

        if not in_events:
            continue

        if stripped.lower().startswith("format:"):
            format_fields = [f.strip().lower() for f in stripped[7:].split(",")]
            continue

        if not stripped.lower().startswith("dialogue:"):
            continue

        # Parse dialogue line
        parts = stripped[9:].split(",", len(format_fields) - 1) if format_fields else stripped[9:].split(",", 9)
        if len(parts) < 3:
            continue

        try:
            if format_fields:
                start_idx = format_fields.index("start")
                end_idx = format_fields.index("end")
                text_idx = format_fields.index("text")
            else:
                start_idx, end_idx, text_idx = 1, 2, -1
        except ValueError:
            continue

        start = parts[start_idx].strip()
        end = parts[end_idx].strip()
        text = parts[text_idx].strip() if text_idx >= 0 else parts[-1].strip()

        # Convert ASS time format (H:MM:SS.CC) to VTT (HH:MM:SS.MMM)
        def _convert_time(t):
            m = re.match(r"(\d+):(\d{2}):(\d{2})\.(\d{2})", t)
            if m:
                h, mi, s, cs = m.groups()
                return f"{int(h):02d}:{mi}:{s}.{cs}0"
            return t

        start = _convert_time(start)
        end = _convert_time(end)

        # Strip ASS formatting tags {\...}
        text = re.sub(r"\{[^}]*\}", "", text)
        # Convert \N to newline
        text = text.replace("\\N", "\n").replace("\\n", "\n")

        if text.strip():
            vtt += f"{start} --> {end}\n{text}\n\n"

    return vtt


def convert_sub_to_vtt(filepath):
    """Read a subtitle file and return WebVTT text."""
    ext = os.path.splitext(filepath)[1].lower()

    # Try common encodings
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "shift_jis"):
        try:
            with open(filepath, "r", encoding=encoding) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        return "WEBVTT\n\n"

    if ext == ".vtt":
        return text
    elif ext == ".srt":
        return _srt_to_vtt(text)
    elif ext in (".ass", ".ssa"):
        return _ass_to_vtt(text)
    return "WEBVTT\n\n"


# ── Helpers ───────────────────────────────────────────────────────────


def _human_size(nbytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def _count_items(path):
    """Count subdirectories and video files in a path."""
    dirs = 0
    videos = 0
    try:
        for entry in os.scandir(path):
            if entry.is_dir():
                dirs += 1
            elif entry.is_file() and os.path.splitext(entry.name)[1].lower() in VIDEO_EXTS:
                videos += 1
    except PermissionError:
        pass
    return dirs, videos


def _find_embedded_subs(video_path):
    """Probe a video file for embedded subtitle streams using ffprobe."""
    if not FFPROBE:
        return []
    try:
        result = subprocess.run(
            [FFPROBE, "-v", "quiet", "-print_format", "json",
             "-show_streams", "-select_streams", "s", video_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        data = _json.loads(result.stdout)
        subs = []
        for s in data.get("streams", []):
            tags = s.get("tags", {})
            label = tags.get("title") or tags.get("language") or f"Track {s['index']}"
            subs.append({
                "stream_index": s["index"],
                "codec": s.get("codec_name", ""),
                "label": label,
            })
        return subs
    except Exception:
        return []


def _extract_sub_to_vtt(video_path, stream_index):
    """Extract an embedded subtitle stream to WebVTT using ffmpeg."""
    if not FFMPEG:
        return None
    try:
        result = subprocess.run(
            [FFMPEG, "-v", "quiet", "-i", video_path,
             "-map", f"0:{stream_index}", "-f", "webvtt", "-"],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception:
        pass
    return None


def _find_subtitles(video_path):
    """Find subtitle files associated with a video file.

    Matches by:
    - Exact stem match: video.mkv → video.srt, video.ass
    - Stem prefix match: video.mkv → video.en.srt, video.Japanese.ass
    """
    video_dir = os.path.dirname(video_path)
    video_stem = os.path.splitext(os.path.basename(video_path))[0]
    subs = []
    try:
        for entry in os.scandir(video_dir):
            if not entry.is_file():
                continue
            ext = os.path.splitext(entry.name)[1].lower()
            if ext not in SUB_EXTS:
                continue
            sub_stem = os.path.splitext(entry.name)[0]
            # Match exact stem or stem prefix (for language tags)
            if sub_stem == video_stem or sub_stem.startswith(video_stem + "."):
                # Extract language tag if present
                if sub_stem == video_stem:
                    label = ext[1:].upper()
                else:
                    tag = sub_stem[len(video_stem) + 1:]
                    label = tag
                subs.append({"path": entry.path, "name": entry.name, "label": label})
    except PermissionError:
        pass
    return sorted(subs, key=lambda s: s["name"])


def _find_adjacent_episodes(video_path, anime_path):
    """Find previous and next video files in the same directory."""
    video_dir = os.path.dirname(video_path)
    video_name = os.path.basename(video_path)
    videos = []
    try:
        for entry in sorted(os.scandir(video_dir), key=lambda e: e.name.lower()):
            if entry.is_file() and os.path.splitext(entry.name)[1].lower() in VIDEO_EXTS:
                videos.append(entry.name)
    except PermissionError:
        pass

    prev_ep = None
    next_ep = None
    try:
        idx = videos.index(video_name)
        if idx > 0:
            prev_ep = videos[idx - 1]
        if idx < len(videos) - 1:
            next_ep = videos[idx + 1]
    except ValueError:
        pass

    # Build URL paths
    rel_dir = os.path.relpath(video_dir, anime_path)
    dir_parts = rel_dir.split(os.sep) if rel_dir != "." else []

    def make_url(name):
        return "/watch/" + "/".join(dir_parts + [name])

    return (
        make_url(prev_ep) if prev_ep else None,
        make_url(next_ep) if next_ep else None,
    )


# ── HTTP Handler ──────────────────────────────────────────────────────


class AnimeHandler(SimpleHTTPRequestHandler):
    """HTTP handler with Range support, styled directory listing, and video player."""

    # Use HTTP/1.1 — required for proper Range/streaming support in browsers
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, anime_path="", **kwargs):
        self._anime_path = anime_path
        super().__init__(*args, directory=anime_path, **kwargs)

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in EXTRA_MIMES:
            return EXTRA_MIMES[ext]
        return super().guess_type(path)

    def _resolve_path(self, url_path):
        """Resolve a URL path to a filesystem path within anime_path."""
        url_path = urllib.parse.unquote(url_path)
        url_path = url_path.split("?", 1)[0].split("#", 1)[0]
        parts = url_path.strip("/").split("/")
        if parts[0]:
            safe = os.path.normpath(os.path.join(self._anime_path, *parts))
        else:
            safe = self._anime_path
        if not safe.startswith(os.path.realpath(self._anime_path)):
            return self._anime_path
        return safe

    def translate_path(self, path):
        """Ensure we stay within the anime directory."""
        return self._resolve_path(path)

    def do_GET(self):
        raw_path = urllib.parse.unquote(self.path.split("?", 1)[0].split("#", 1)[0])

        # /watch/... → player page
        if raw_path.startswith("/watch/"):
            return self._serve_player(raw_path[7:])

        # /sub/... → subtitle as WebVTT
        if raw_path.startswith("/sub/"):
            return self._serve_subtitle(raw_path[5:])

        # /embsub/{stream_index}/... → extract embedded subtitle as WebVTT
        if raw_path.startswith("/embsub/"):
            return self._serve_embedded_subtitle(raw_path[8:])

        # /raw/... → direct file (for download link in player)
        if raw_path.startswith("/raw/"):
            path = self._resolve_path(raw_path[4:])
            if os.path.isfile(path):
                return self._serve_file(path)
            self.send_error(404)
            return

        path = self.translate_path(self.path)

        if os.path.isdir(path):
            return self._serve_directory(path)

        if not os.path.isfile(path):
            self.send_error(404)
            return

        self._serve_file(path)

    def _add_cors(self):
        """Add CORS headers — safe on a LAN server."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, Accept-Ranges")
        self.send_header("Connection", "keep-alive")

    def _serve_file(self, path):
        """Serve a file with Range support."""
        range_header = self.headers.get("Range")
        if range_header:
            return self._serve_range(path, range_header)

        try:
            file_size = os.path.getsize(path)
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self._add_cors()
            self.end_headers()
            with open(path, "rb") as f:
                self._copy_chunks(f, file_size)
        except (OSError, BrokenPipeError):
            pass

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self._add_cors()
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.end_headers()

    def do_HEAD(self):
        path = self.translate_path(self.path)
        if os.path.isfile(path):
            file_size = os.path.getsize(path)
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self._add_cors()
            self.end_headers()
        elif os.path.isdir(path):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
        else:
            self.send_error(404)

    def _serve_range(self, path, range_header):
        """Handle HTTP Range request for video seeking."""
        file_size = os.path.getsize(path)
        try:
            byte_range = range_header.replace("bytes=", "").strip()
            parts = byte_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            self.send_error(416, "Invalid range")
            return

        if start >= file_size or end >= file_size:
            end = file_size - 1
        if start > end:
            self.send_error(416)
            return

        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self._add_cors()
        self.end_headers()

        try:
            with open(path, "rb") as f:
                f.seek(start)
                self._copy_chunks(f, length)
        except (OSError, BrokenPipeError):
            pass

    def _copy_chunks(self, f, remaining, chunk_size=1024 * 1024):
        """Stream file in 1MB chunks."""
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            self.wfile.write(chunk)
            remaining -= len(chunk)

    def _serve_embedded_subtitle(self, path_with_index):
        """Extract and serve an embedded subtitle stream as WebVTT."""
        # Path format: {stream_index}/{video/path}
        parts = path_with_index.split("/", 1)
        if len(parts) < 2:
            self.send_error(400)
            return
        try:
            stream_index = int(parts[0])
        except ValueError:
            self.send_error(400)
            return

        fs_path = self._resolve_path(parts[1])
        if not os.path.isfile(fs_path):
            self.send_error(404)
            return

        data = _extract_sub_to_vtt(fs_path, stream_index)
        if not data:
            self.send_error(500, "Failed to extract subtitle")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/vtt; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._add_cors()
        self.end_headers()
        self.wfile.write(data)

    def _serve_subtitle(self, sub_path):
        """Serve a subtitle file converted to WebVTT."""
        fs_path = self._resolve_path(sub_path)
        if not os.path.isfile(fs_path):
            self.send_error(404)
            return

        ext = os.path.splitext(fs_path)[1].lower()
        if ext not in SUB_EXTS:
            self.send_error(404)
            return

        vtt_text = convert_sub_to_vtt(fs_path)
        data = vtt_text.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/vtt; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _serve_player(self, video_rel_path):
        """Serve an HTML video player page with subtitle support."""
        fs_path = self._resolve_path(video_rel_path)
        if not os.path.isfile(fs_path):
            self.send_error(404)
            return

        ext = os.path.splitext(fs_path)[1].lower()
        if ext not in VIDEO_EXTS:
            self.send_error(400, "Not a video file")
            return

        video_name = os.path.basename(fs_path)
        video_stem = os.path.splitext(video_name)[0]

        # URL to the raw video file (for the <video> src)
        video_url = "/" + urllib.parse.quote(
            os.path.relpath(fs_path, self._anime_path), safe="/"
        )

        # Find subtitles — external files first, then embedded streams
        subs = _find_subtitles(fs_path)
        all_sub_labels = []
        sub_tracks = ""
        for i, sub in enumerate(subs):
            sub_rel = os.path.relpath(sub["path"], self._anime_path)
            sub_url = "/sub/" + urllib.parse.quote(sub_rel, safe="/")
            default = " default" if i == 0 else ""
            label = html.escape(sub["label"])
            sub_tracks += f'<track kind="subtitles" src="{sub_url}" label="{label}" srclang="{label}"{default}>\n'
            all_sub_labels.append(sub["label"])

        # Embedded subtitles (extracted via ffmpeg)
        embedded = _find_embedded_subs(fs_path)
        video_rel = os.path.relpath(fs_path, self._anime_path)
        for emb in embedded:
            idx = emb["stream_index"]
            emb_url = f"/embsub/{idx}/" + urllib.parse.quote(video_rel, safe="/")
            default = " default" if not sub_tracks else ""
            label = html.escape(emb["label"])
            sub_tracks += f'<track kind="subtitles" src="{emb_url}" label="{label} (embedded)" srclang="en"{default}>\n'
            all_sub_labels.append(emb["label"] + " (embedded)")

        # Find prev/next episodes
        prev_url, next_url = _find_adjacent_episodes(fs_path, self._anime_path)

        # Back link (to parent directory)
        rel = os.path.relpath(os.path.dirname(fs_path), self._anime_path)
        back_url = "/" + ("/".join(rel.split(os.sep)) + "/" if rel != "." else "")

        # Download link
        dl_url = "/raw" + video_url

        # Navigation buttons
        nav_html = '<div class="nav-buttons">'
        if prev_url:
            nav_html += f'<a href="{html.escape(prev_url)}">Prev</a>'
        if next_url:
            nav_html += f'<a href="{html.escape(next_url)}">Next</a>'
        nav_html += '</div>'

        # Subtitle selector JS
        total_subs = len(all_sub_labels)
        sub_selector_html = ""
        sub_js = ""
        if total_subs > 1:
            options = ""
            for i, label in enumerate(all_sub_labels):
                selected = " selected" if i == 0 else ""
                options += f'<option value="{i}"{selected}>{html.escape(label)}</option>'
            sub_selector_html = f'<span class="sub-selector">Subs: <select id="subSelect" onchange="switchSub(this.value)">{options}<option value="-1">Off</option></select></span>'
            sub_js = """
function switchSub(idx) {
  var v = document.getElementById('player');
  for (var i = 0; i < v.textTracks.length; i++) {
    v.textTracks[i].mode = (i == idx) ? 'showing' : 'hidden';
  }
}
"""
        elif total_subs == 1:
            sub_js = """
document.addEventListener('DOMContentLoaded', function() {
  var v = document.getElementById('player');
  if (v.textTracks.length > 0) v.textTracks[0].mode = 'showing';
});
"""

        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(video_stem)} — AniHermes Player</title>
<style>{PLAYER_CSS}</style>
</head>
<body>
<div class="player-wrap">
<video id="player" controls autoplay crossorigin="anonymous" playsinline>
<source src="{html.escape(video_url)}">
{sub_tracks}Your browser does not support the video tag.
</video>
<div id="error-banner" style="display:none; background:#da3633; color:#fff; padding:0.8rem 1rem; text-align:center; font-size:0.9rem;">
  <span id="error-msg">This video format may not be supported by your browser.</span>
  <a href="{html.escape(dl_url)}" download style="color:#fff; text-decoration:underline; margin-left:1rem;">Download file</a>
  <span style="margin-left:0.5rem;">or open in VLC</span>
</div>
<div class="controls">
<a href="{html.escape(back_url)}">Back</a>
<span class="title">{html.escape(video_stem)}</span>
{sub_selector_html}
<a class="btn btn-dl" href="{html.escape(dl_url)}" download>Download</a>
{nav_html}
</div>
</div>
<script>
{sub_js}
// Error handling
var v = document.getElementById('player');
v.addEventListener('error', function(e) {{
  var banner = document.getElementById('error-banner');
  var msg = document.getElementById('error-msg');
  var err = v.error;
  if (err) {{
    if (err.code === 4) {{
      msg.textContent = 'Your browser cannot play this format. Try Chrome for MKV, or download and open in VLC/mpv.';
    }} else {{
      msg.textContent = 'Error loading video (code ' + err.code + '). Try downloading the file instead.';
    }}
  }}
  banner.style.display = 'block';
}});
v.addEventListener('stalled', function() {{
  setTimeout(function() {{
    if (v.readyState < 2 && v.networkState === 2) {{
      document.getElementById('error-banner').style.display = 'block';
      document.getElementById('error-msg').textContent = 'Video is loading slowly. If nothing happens, try downloading and opening in VLC.';
    }}
  }}, 8000);
}});
// Keyboard shortcuts
document.addEventListener('keydown', function(e) {{
  var v = document.getElementById('player');
  if (e.key === 'ArrowLeft') {{ v.currentTime -= 5; e.preventDefault(); }}
  if (e.key === 'ArrowRight') {{ v.currentTime += 5; e.preventDefault(); }}
  if (e.key === ' ') {{ v.paused ? v.play() : v.pause(); e.preventDefault(); }}
  if (e.key === 'f') {{ document.fullscreenElement ? document.exitFullscreen() : v.requestFullscreen(); }}
}});
// Auto-play next episode when current one ends
var v = document.getElementById('player');
v.addEventListener('ended', function() {{
  var nextUrl = {f'"{html.escape(next_url)}"' if next_url else 'null'};
  if (nextUrl) {{ window.location.href = nextUrl; }}
}});
</script>
</body>
</html>"""

        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_directory(self, fs_path):
        """Serve a styled HTML directory listing."""
        rel = os.path.relpath(fs_path, self._anime_path)
        if rel == ".":
            rel = ""

        url_parts = rel.split(os.sep) if rel else []

        # Build breadcrumb
        breadcrumb = '<a href="/">Library</a>'
        for i, part in enumerate(url_parts):
            link = "/" + "/".join(url_parts[: i + 1]) + "/"
            breadcrumb += f' / <a href="{html.escape(link)}">{html.escape(part)}</a>'

        # Scan directory
        try:
            entries = sorted(os.scandir(fs_path), key=lambda e: e.name.lower())
        except PermissionError:
            self.send_error(403)
            return

        dirs = [e for e in entries if e.is_dir() and not e.name.startswith(".")]
        files = [e for e in entries if e.is_file() and not e.name.startswith(".")]
        videos = [f for f in files if os.path.splitext(f.name)[1].lower() in VIDEO_EXTS]
        other_files = [f for f in files if f not in videos]

        body_parts = []

        # Back link
        if rel:
            parent = "/" + "/".join(url_parts[:-1])
            if parent != "/":
                parent += "/"
            body_parts.append(f'<a class="back" href="{html.escape(parent)}">.. back</a>')

        # Directory cards (for series/seasons)
        if dirs:
            body_parts.append('<div class="grid">')
            for d in dirs:
                sub_dirs, sub_videos = _count_items(d.path)
                meta_parts = []
                if sub_dirs:
                    meta_parts.append(f"{sub_dirs} folder{'s' if sub_dirs != 1 else ''}")
                if sub_videos:
                    meta_parts.append(f"{sub_videos} episode{'s' if sub_videos != 1 else ''}")
                meta = " &middot; ".join(meta_parts) if meta_parts else "empty"
                link = "/" + "/".join(url_parts + [d.name]) + "/"
                body_parts.append(f'''<a href="{html.escape(link)}" style="text-decoration:none;color:inherit"><div class="card">
<div class="title">{html.escape(d.name)}</div>
<div class="meta">{meta}</div>
</div></a>''')
            body_parts.append("</div>")

        # Video file list (episodes) — link to player
        if videos:
            body_parts.append('<ul class="list">')
            for v in videos:
                size = _human_size(v.stat().st_size)
                watch_link = "/watch/" + "/".join(url_parts + [v.name])
                raw_link = "/" + "/".join(url_parts + [v.name])

                # Check for subtitles
                subs = _find_subtitles(v.path)
                sub_info = f'<span class="subs">{len(subs)} sub{"s" if len(subs) != 1 else ""}</span>' if subs else ""

                body_parts.append(
                    f'<li>'
                    f'<a class="btn btn-play" href="{html.escape(watch_link)}">Watch</a> '
                    f'<a href="{html.escape(watch_link)}">{html.escape(v.name)}</a> '
                    f'<span class="size">{size}</span> {sub_info}'
                    f'</li>'
                )
            body_parts.append("</ul>")

        # Other files
        if other_files:
            body_parts.append('<ul class="list">')
            for f in other_files:
                size = _human_size(f.stat().st_size)
                link = "/" + "/".join(url_parts + [f.name])
                body_parts.append(
                    f'<li><a href="{html.escape(link)}">{html.escape(f.name)}</a> '
                    f'<span class="size">{size}</span></li>'
                )
            body_parts.append("</ul>")

        if not dirs and not files:
            body_parts.append('<p style="color:#8b949e">This folder is empty.</p>')

        title = url_parts[-1] if url_parts else "Anime Library"
        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — AniHermes</title>
<style>{CSS}</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="breadcrumb">{breadcrumb}</div>
{"".join(body_parts)}
</body>
</html>"""

        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        """Quieter logging — only errors."""
        if args and isinstance(args[0], str) and args[0].startswith("4"):
            super().log_message(format, *args)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def get_lan_ip():
    """Get the LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def get_library_stats(anime_path):
    """Quick stats: series count, total size."""
    series = 0
    total_size = 0
    try:
        for entry in os.scandir(anime_path):
            if entry.is_dir() and not entry.name.startswith("."):
                series += 1
        for root, _dirs, files in os.walk(anime_path):
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except (OSError, PermissionError):
        pass
    return series, total_size


def start_server(anime_path, bind, port):
    """Start the media server, daemonize."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            print(f"Server already running (PID {pid})")
            return
        except (ProcessLookupError, ValueError):
            os.remove(PID_FILE)

    if not os.path.isdir(anime_path):
        print(f"ERROR: Anime path does not exist: {anime_path}")
        sys.exit(1)

    # Fork to background
    pid = os.fork()
    if pid > 0:
        # Parent — wait briefly for child to start, then report
        lan_ip = get_lan_ip()
        series, total_size = get_library_stats(anime_path)
        print(f"AniHermes Media Server started (PID {pid})")
        print(f"URL: http://{lan_ip}:{port}/")
        print(f"Library: {series} series, {_human_size(total_size)}")
        print(f"Serving: {anime_path}")
        return

    # Child — daemonize
    os.setsid()
    sys.stdin = open(os.devnull)
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

    # Write PID file
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    def handler_factory(*args, **kwargs):
        return AnimeHandler(*args, anime_path=anime_path, **kwargs)

    server = ThreadedHTTPServer((bind, port), handler_factory)

    def cleanup(sig, frame):
        server.shutdown()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    server.serve_forever()


def stop_server():
    """Stop the running server."""
    if not os.path.exists(PID_FILE):
        print("Server is not running.")
        return

    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"Server stopped (PID {pid})")
    except ProcessLookupError:
        print("Server was not running (stale PID file).")
    except ValueError:
        print("Invalid PID file.")
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


def server_status(port):
    """Show server status."""
    if not os.path.exists(PID_FILE):
        print("Status: stopped")
        return

    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        lan_ip = get_lan_ip()
        print(f"Status: running (PID {pid})")
        print(f"URL: http://{lan_ip}:{port}/")
    except (ProcessLookupError, ValueError):
        print("Status: stopped (stale PID file)")
        os.remove(PID_FILE)


def main():
    parser = argparse.ArgumentParser(description="AniHermes LAN Media Server")
    parser.add_argument("command", choices=["start", "stop", "status"], help="Server command")
    parser.add_argument("--port", type=int, default=None, help="Override port (default from config or 8888)")
    parser.add_argument("--bind", default=None, help="Bind address (default from config or 0.0.0.0)")
    args = parser.parse_args()

    # Load config
    try:
        config = load_config()
    except FileNotFoundError:
        config = {}

    server_conf = config.get("server", {})
    port = args.port or int(server_conf.get("port", 8888))
    bind = args.bind or server_conf.get("bind", "0.0.0.0")
    anime_path = config.get("storage", {}).get("anime_path", os.path.expanduser("~/Anime"))

    if args.command == "start":
        start_server(anime_path, bind, port)
    elif args.command == "stop":
        stop_server()
    elif args.command == "status":
        server_status(port)


if __name__ == "__main__":
    main()
