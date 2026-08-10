"""
YouTube Video & MP3 Audio Downloader Flask Backend with Protected Admin Dashboard
=================================================================================
Powered by Flask, yt-dlp, Cobalt API, Piped API, and YouTube oEmbed.
"""

import os
import re
import uuid
import time
import json
import threading
import math
import shutil
import urllib.request
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import yt_dlp

try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = None

app = Flask(__name__)
app.secret_key = "cyber_tube_daraab_khan_secret_key_2026"

# Admin Credentials
ADMIN_USERNAME = "daraabkhan09"
ADMIN_PASSWORD = "KingKhan007"

# Directory & Log Persistence setup
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
LOGS_FILE = os.path.join(os.path.dirname(__file__), "download_logs.json")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Application startup time
SERVER_START_TIME = time.time()


def load_persistent_logs():
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("[-] Warning: Failed to parse download_logs.json:", e)
            return []
    return []


def save_persistent_logs(logs):
    try:
        with open(LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[-] Error saving persistent download_logs.json:", e)


# In-memory tracking & Permanent history logs
download_tracker = {}
download_history_logs = load_persistent_logs()
tracker_lock = threading.Lock()


def extract_youtube_id(url):
    url = url.strip()
    if "youtu.be/" in url:
        part = url.split("youtu.be/")[1]
        video_id = part.split("?")[0].split("&")[0].split("/")[0][:11]
        if len(video_id) == 11:
            return video_id
    if "v=" in url:
        part = url.split("v=")[1]
        video_id = part.split("&")[0].split("?")[0][:11]
        if len(video_id) == 11:
            return video_id
    if "shorts/" in url:
        part = url.split("shorts/")[1]
        video_id = part.split("?")[0].split("&")[0].split("/")[0][:11]
        if len(video_id) == 11:
            return video_id

    match = re.search(r"([0-9A-Za-z_-]{11})", url)
    if match:
        return match.group(1)
    return None


def fetch_youtube_oembed(video_id):
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        req = urllib.request.Request(
            oembed_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "title": data.get("title", "YouTube Video"),
                    "channel": data.get("author_name", "YouTube Channel"),
                    "thumbnail": data.get("thumbnail_url") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                }
    except Exception:
        pass
    return None


def get_cobalt_download_url(url, is_audio, height):
    """Fetches high-speed direct download link from Cobalt API."""
    cobalt_endpoints = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json"
    ]
    payload = {
        "url": url,
        "vQuality": str(height) if not is_audio else "720",
        "isAudioOnly": is_audio,
        "aFormat": "mp3" if is_audio else "best"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    for endpoint in cobalt_endpoints:
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status in [200, 201]:
                    data = json.loads(resp.read().decode("utf-8"))
                    direct_url = data.get("url")
                    if direct_url:
                        print(f"[+] Cobalt API download link success ({endpoint})")
                        return direct_url
        except Exception as e:
            print(f"[-] Cobalt endpoint {endpoint} error:", e)
            continue
    return None


PIPED_API_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.yt",
    "https://pipedapi.adminforge.de"
]


def fetch_piped_streams(video_id):
    for instance in PIPED_API_INSTANCES:
        api_url = f"{instance}/streams/{video_id}"
        try:
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
    return None


CLIENT_FALLBACKS = [
    ["ios"],
    ["mweb"],
    ["android"],
    ["tv"],
    ["web"]
]


def extract_with_client_fallback(url, download=False, base_opts=None):
    if base_opts is None:
        base_opts = {}

    opts_to_use = {**base_opts}
    if FFMPEG_PATH:
        opts_to_use["ffmpeg_location"] = FFMPEG_PATH

    last_error = None
    for client in CLIENT_FALLBACKS:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "extractor_args": {
                "youtube": {
                    "player_client": client
                }
            },
            **opts_to_use
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(url, download=download)
                if res:
                    return res
        except Exception as e:
            last_error = e
            continue

    if last_error:
        raise last_error
    raise RuntimeError("Could not process request.")


def format_bytes(bytes_num):
    if not bytes_num:
        return "Unknown size"
    sizes = ["B", "KB", "MB", "GB"]
    i = int(math.floor(math.log(bytes_num, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_num / p, 2)
    return f"{s} {sizes[i]}"


def format_seconds(sec):
    if not sec:
        return "--"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s" if m > 0 else f"{s}s"


@app.route("/")
def index():
    return render_template("index.html")


# ==========================================================================
# Admin Authentication & Dashboard Routes
# ==========================================================================

@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return render_template("admin_login.html")
    return render_template("admin.html")


@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        return jsonify({"success": True, "message": "Authentication successful!"})
    else:
        return jsonify({"error": "Invalid Admin Username or Password."}), 401


@app.route("/admin/logout", methods=["GET", "POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_dashboard"))


@app.route("/api/info", methods=["POST"])
def get_video_info():
    data = request.get_json() or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "Please provide a valid YouTube URL"}), 400

    video_id = extract_youtube_id(url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL format."}), 400

    title = "YouTube Video"
    channel = "YouTube Channel"
    thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    duration = 0
    views = "N/A"

    oembed_data = fetch_youtube_oembed(video_id)
    if oembed_data:
        title = oembed_data["title"]
        channel = oembed_data["channel"]
        thumbnail = oembed_data["thumbnail"]

    try:
        info = extract_with_client_fallback(url, download=False, base_opts={"skip_download": True})
        if info:
            title = info.get("title", title)
            channel = info.get("uploader") or info.get("channel") or channel
            thumbnail = info.get("thumbnail") or thumbnail
            duration = info.get("duration", duration)
            v_cnt = info.get("view_count", 0)
            views = f"{v_cnt:,}" if v_cnt else views
    except Exception:
        pass

    video_options = [
        {"height": 1080, "label": "1080p Full HD", "badge": "HD", "format_type": "video", "available": True},
        {"height": 720, "label": "720p HD", "badge": "HD", "format_type": "video", "available": True},
        {"height": 480, "label": "480p SD", "badge": "SD", "format_type": "video", "available": True},
        {"height": 360, "label": "360p", "badge": "SD", "format_type": "video", "available": True}
    ]
    audio_options = [
        {"id": "mp3_320", "label": "MP3 Audio (High Quality 320kbps)", "badge": "HQ MP3", "format_type": "audio", "ext": "mp3", "bitrate": "320"},
        {"id": "mp3_192", "label": "MP3 Audio (Standard 192kbps)", "badge": "MP3", "format_type": "audio", "ext": "mp3", "bitrate": "192"},
        {"id": "m4a", "label": "M4A Audio (AAC)", "badge": "M4A", "format_type": "audio", "ext": "m4a", "bitrate": "128"}
    ]

    return jsonify({
        "success": True,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": title,
        "thumbnail": thumbnail,
        "duration": format_seconds(duration),
        "channel": channel,
        "views": views,
        "video_options": video_options,
        "audio_options": audio_options
    })


def run_download_thread(download_id, url, is_audio, height, bitrate, ext, client_ip):
    output_template = os.path.join(DOWNLOAD_DIR, f"{download_id}.%(ext)s")
    start_timestamp = time.time()
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def progress_hook(d):
        with tracker_lock:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed", 0)
                eta = d.get("eta")

                pct = (downloaded / total * 100) if total > 0 else 0
                
                download_tracker[download_id].update({
                    "status": "downloading",
                    "percent": round(pct, 1),
                    "downloaded_str": format_bytes(downloaded),
                    "total_str": format_bytes(total),
                    "speed_str": f"{format_bytes(speed)}/s" if speed else "Calculating...",
                    "eta_str": format_seconds(eta)
                })
            elif d.get("status") == "finished":
                download_tracker[download_id].update({
                    "status": "processing",
                    "percent": 98.0,
                    "status_msg": "Processing & Finalizing File..."
                })

    download_success = False
    title = "YouTube Video"
    thumbnail = ""
    final_path = None
    direct_stream_url = None

    # Engine 1: Cobalt High-Speed API
    direct_stream_url = get_cobalt_download_url(url, is_audio, height)
    if direct_stream_url:
        download_success = True
        video_id = extract_youtube_id(url)
        oembed = fetch_youtube_oembed(video_id) if video_id else None
        if oembed:
            title = oembed["title"]
            thumbnail = oembed["thumbnail"]

    # Engine 2: yt-dlp Local Server Extraction (if Cobalt busy)
    if not download_success:
        try:
            if is_audio:
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": output_template,
                    "progress_hooks": [progress_hook],
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3" if ext == "mp3" else "m4a",
                        "preferredquality": bitrate,
                    }],
                }
            else:
                format_str = f"best[height<={height}][ext=mp4]/bestvideo[height<={height}]+bestaudio/best"
                ydl_opts = {
                    "format": format_str,
                    "outtmpl": output_template,
                    "progress_hooks": [progress_hook],
                }

            info = extract_with_client_fallback(url, download=True, base_opts=ydl_opts)
            if info:
                title = info.get("title", title)
                thumbnail = info.get("thumbnail", thumbnail)

            final_ext = ext if is_audio else "mp4"
            target_path = os.path.join(DOWNLOAD_DIR, f"{download_id}.{final_ext}")

            if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                final_path = target_path
                download_success = True
            else:
                for file in os.listdir(DOWNLOAD_DIR):
                    if file.startswith(download_id):
                        fp = os.path.join(DOWNLOAD_DIR, file)
                        if os.path.getsize(fp) > 0:
                            final_path = fp
                            final_ext = file.split(".")[-1]
                            download_success = True
                            break
        except Exception as e:
            print(f"[-] yt-dlp server download log for {download_id}:", e)

    # Engine 3: Piped Stream Fallback
    if not download_success:
        video_id = extract_youtube_id(url)
        if video_id:
            piped_data = fetch_piped_streams(video_id)
            if piped_data:
                title = piped_data.get("title", title)
                thumbnail = piped_data.get("thumbnailUrl", thumbnail)

                if is_audio:
                    audio_streams = piped_data.get("audioStreams", [])
                    if audio_streams:
                        direct_stream_url = audio_streams[0].get("url")
                else:
                    video_streams = piped_data.get("videoStreams", [])
                    for s in video_streams:
                        if s.get("quality") == f"{height}p" or s.get("height") == height:
                            direct_stream_url = s.get("url")
                            break
                    if not direct_stream_url and video_streams:
                        direct_stream_url = video_streams[0].get("url")

                if direct_stream_url:
                    download_success = True

    elapsed_sec = round(time.time() - start_timestamp, 1)

    if download_success:
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        final_ext = ext if is_audio else "mp4"
        download_filename = f"{clean_title}.{final_ext}"
        format_label = f"MP3 ({bitrate}kbps)" if is_audio else f"Video ({height}p)"
        file_size_bytes = os.path.getsize(final_path) if final_path and os.path.exists(final_path) else 0

        with tracker_lock:
            download_tracker[download_id].update({
                "status": "completed",
                "percent": 100.0,
                "file_path": final_path,
                "direct_url": direct_stream_url,
                "download_name": download_filename,
                "status_msg": "Download Ready!"
            })

            download_history_logs.append({
                "id": download_id,
                "title": title,
                "url": url,
                "thumbnail": thumbnail,
                "format_label": format_label,
                "is_audio": is_audio,
                "download_name": download_filename,
                "file_size_str": format_bytes(file_size_bytes) if file_size_bytes else "High-Speed Stream",
                "file_size_bytes": file_size_bytes,
                "timestamp": time_str,
                "duration_sec": f"{elapsed_sec}s",
                "client_ip": client_ip,
                "status": "completed"
            })
            save_persistent_logs(download_history_logs)

    else:
        with tracker_lock:
            download_tracker[download_id].update({
                "status": "error",
                "error_msg": "Download stream unavailable. Please try again."
            })
            download_history_logs.append({
                "id": download_id,
                "title": "Failed Download",
                "url": url,
                "thumbnail": "",
                "format_label": "MP3" if is_audio else f"Video ({height}p)",
                "is_audio": is_audio,
                "download_name": "--",
                "file_size_str": "0 B",
                "file_size_bytes": 0,
                "timestamp": time_str,
                "duration_sec": f"{elapsed_sec}s",
                "client_ip": client_ip,
                "status": "failed",
                "error_detail": "All download engines exhausted"
            })
            save_persistent_logs(download_history_logs)


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    is_audio = data.get("is_audio", False)
    height = data.get("height", 720)
    bitrate = data.get("bitrate", "320")
    ext = data.get("ext", "mp3")

    if not url:
        return jsonify({"error": "Missing YouTube URL"}), 400

    download_id = str(uuid.uuid4())
    client_ip = request.remote_addr or "127.0.0.1"

    with tracker_lock:
        download_tracker[download_id] = {
            "status": "starting",
            "percent": 0.0,
            "speed_str": "0 MB/s",
            "eta_str": "--",
            "downloaded_str": "0 B",
            "total_str": "Calculating...",
            "status_msg": "Initializing Stream..."
        }

    t = threading.Thread(
        target=run_download_thread,
        args=(download_id, url, is_audio, height, bitrate, ext, client_ip),
        daemon=True
    )
    t.start()

    return jsonify({"success": True, "download_id": download_id})


@app.route("/api/progress/<download_id>", methods=["GET"])
def get_progress(download_id):
    with tracker_lock:
        data = download_tracker.get(download_id)
        if not data:
            return jsonify({"error": "Invalid Download ID"}), 404
        return jsonify(data)


@app.route("/api/file/<download_id>", methods=["GET"])
def get_file(download_id):
    with tracker_lock:
        data = download_tracker.get(download_id)
        if not data or data.get("status") != "completed":
            return jsonify({"error": "File not ready for download"}), 400
        
        file_path = data.get("file_path")
        direct_url = data.get("direct_url")
        download_name = data.get("download_name", "download.mp4")

    if direct_url:
        return redirect(direct_url)
    elif file_path and os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=download_name)
    else:
        return jsonify({"error": "File not found on server"}), 404


# ==========================================================================
# Protected Admin Dashboard Analytics & Management API Endpoints
# ==========================================================================

@app.route("/api/admin/stats", methods=["GET"])
def get_admin_stats():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized Admin Access"}), 401

    total_disk, used_disk, free_disk = shutil.disk_usage(DOWNLOAD_DIR)
    disk_percent = round((used_disk / total_disk) * 100, 1)

    cache_files = os.listdir(DOWNLOAD_DIR)
    cache_size_bytes = sum(
        os.path.getsize(os.path.join(DOWNLOAD_DIR, f))
        for f in cache_files if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))
    )

    with tracker_lock:
        active_downloads = sum(1 for d in download_tracker.values() if d.get("status") in ["downloading", "starting", "processing"])
        total_logs = len(download_history_logs)
        completed_logs = sum(1 for d in download_history_logs if d.get("status") == "completed")
        failed_logs = sum(1 for d in download_history_logs if d.get("status") == "failed")
        audio_logs = sum(1 for d in download_history_logs if d.get("is_audio"))
        video_logs = total_logs - audio_logs

    uptime_sec = round(time.time() - SERVER_START_TIME)

    return jsonify({
        "disk_total_gb": round(total_disk / (1024**3), 2),
        "disk_used_gb": round(used_disk / (1024**3), 2),
        "disk_free_gb": round(free_disk / (1024**3), 2),
        "disk_percent": disk_percent,
        "cache_files_count": len(cache_files),
        "cache_total_size": format_bytes(cache_size_bytes),
        "active_downloads": active_downloads,
        "total_downloads": total_logs,
        "completed_count": completed_logs,
        "failed_count": failed_logs,
        "audio_count": audio_logs,
        "video_count": video_logs,
        "uptime": format_seconds(uptime_sec)
    })


@app.route("/api/admin/logs", methods=["GET"])
def get_admin_logs():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized Admin Access"}), 401

    with tracker_lock:
        logs = list(reversed(download_history_logs))
    return jsonify({"success": True, "logs": logs})


@app.route("/api/admin/clear-cache", methods=["POST"])
def clear_cache():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized Admin Access"}), 401

    try:
        count = 0
        for f in os.listdir(DOWNLOAD_DIR):
            fp = os.path.join(DOWNLOAD_DIR, f)
            if os.path.isfile(fp):
                os.remove(fp)
                count += 1
        return jsonify({"success": True, "message": f"Cleared {count} cached files from server disk."})
    except Exception as e:
        return jsonify({"error": f"Failed to clear cache: {str(e)}"}), 500


@app.route("/api/admin/clear-logs", methods=["POST"])
def clear_all_logs():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized Admin Access"}), 401

    global download_history_logs
    with tracker_lock:
        download_history_logs = []
        save_persistent_logs(download_history_logs)

    return jsonify({"success": True, "message": "All download history logs cleared permanently."})


@app.route("/api/admin/delete-log/<download_id>", methods=["POST", "DELETE"])
def delete_log_entry(download_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized Admin Access"}), 401

    global download_history_logs
    with tracker_lock:
        download_history_logs = [log for log in download_history_logs if log.get("id") != download_id]
        save_persistent_logs(download_history_logs)
        
        if download_id in download_tracker:
            data = download_tracker.pop(download_id, None)
            if data and data.get("file_path") and os.path.exists(data["file_path"]):
                try:
                    os.remove(data["file_path"])
                except Exception:
                    pass

    return jsonify({"success": True, "message": f"Deleted log {download_id}."})


if __name__ == "__main__":
    print("[+] Starting YouTube Video & MP3 Downloader Server on http://localhost:5000...")
    app.run(host="0.0.0.0", port=5000, debug=True)
