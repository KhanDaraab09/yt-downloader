"""
YouTube Video & MP3 Audio Downloader Flask Backend with Protected Admin Dashboard
=================================================================================
Powered by Flask & yt-dlp for high-speed YouTube metadata parsing, 
video quality resolution downloads, MP3 audio conversion, and Admin Analytics.
"""

import os
import uuid
import time
import json
import threading
import math
import shutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import yt_dlp

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
    """Loads historical download logs permanently from JSON disk file."""
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("[-] Warning: Failed to parse download_logs.json:", e)
            return []
    return []


def save_persistent_logs(logs):
    """Saves historical download logs permanently to JSON disk file."""
    try:
        with open(LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[-] Error saving persistent download_logs.json:", e)


# In-memory tracking & Permanent history logs
download_tracker = {}
download_history_logs = load_persistent_logs()
tracker_lock = threading.Lock()

# Common yt-dlp Options for Bypassing YouTube Datacenter Bot Verification
YTDLP_COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "geo_bypass": True,
    "user_agent": "com.google.android.youtube/19.29.37 (Linux; U; Android 11; en_US) gzip",
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"],
            "player_skip": ["webpage", "configs"],
        }
    },
}


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

    ydl_opts = {
        **YTDLP_COMMON_OPTS,
        "extract_flat": False,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({"error": "Could not extract video metadata"}), 400

            title = info.get("title", "YouTube Video")
            thumbnail = info.get("thumbnail") or (info.get("thumbnails")[-1]["url"] if info.get("thumbnails") else "")
            duration = info.get("duration", 0)
            channel = info.get("uploader") or info.get("channel") or "Unknown Channel"
            view_count = info.get("view_count", 0)
            webpage_url = info.get("webpage_url") or url

            formats = info.get("formats", [])
            heights = set()
            video_options = []

            for f in formats:
                h = f.get("height")
                vcodec = f.get("vcodec")
                if h and h >= 240 and vcodec != "none":
                    heights.add(h)

            sorted_heights = sorted(list(heights), reverse=True)
            
            target_resolutions = [1080, 720, 480, 360]
            for res in target_resolutions:
                is_available = any(h >= res - 30 and h <= res + 30 for h in sorted_heights) or (res <= 720)
                video_options.append({
                    "height": res,
                    "label": f"{res}p Full HD" if res >= 1080 else (f"{res}p HD" if res >= 720 else f"{res}p SD"),
                    "badge": "HD" if res >= 720 else "SD",
                    "format_type": "video",
                    "available": is_available
                })

            audio_options = [
                {
                    "id": "mp3_320",
                    "label": "MP3 Audio (High Quality 320kbps)",
                    "badge": "HQ MP3",
                    "format_type": "audio",
                    "ext": "mp3",
                    "bitrate": "320"
                },
                {
                    "id": "mp3_192",
                    "label": "MP3 Audio (Standard 192kbps)",
                    "badge": "MP3",
                    "format_type": "audio",
                    "ext": "mp3",
                    "bitrate": "192"
                },
                {
                    "id": "m4a",
                    "label": "M4A Audio (AAC)",
                    "badge": "M4A",
                    "format_type": "audio",
                    "ext": "m4a",
                    "bitrate": "128"
                }
            ]

            return jsonify({
                "success": True,
                "url": webpage_url,
                "title": title,
                "thumbnail": thumbnail,
                "duration": format_seconds(duration),
                "channel": channel,
                "views": f"{view_count:,}" if view_count else "N/A",
                "video_options": video_options,
                "audio_options": audio_options
            })

    except Exception as e:
        print("[-] yt-dlp error:", e)
        return jsonify({"error": f"Failed to parse video link: {str(e)}"}), 400


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
                    "status_msg": "Processing & Converting File..."
                })

    try:
        if is_audio:
            ydl_opts = {
                **YTDLP_COMMON_OPTS,
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
            format_str = f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
            ydl_opts = {
                **YTDLP_COMMON_OPTS,
                "format": format_str,
                "outtmpl": output_template,
                "progress_hooks": [progress_hook],
                "merge_output_format": "mp4",
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "download")
            thumbnail = info.get("thumbnail") or ""

        final_ext = ext if is_audio else "mp4"
        expected_filename = f"{download_id}.{final_ext}"
        final_path = os.path.join(DOWNLOAD_DIR, expected_filename)

        if not os.path.exists(final_path):
            for file in os.listdir(DOWNLOAD_DIR):
                if file.startswith(download_id):
                    final_path = os.path.join(DOWNLOAD_DIR, file)
                    final_ext = file.split(".")[-1]
                    break

        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        download_filename = f"{clean_title}.{final_ext}"
        file_size_bytes = os.path.getsize(final_path) if os.path.exists(final_path) else 0
        elapsed_sec = round(time.time() - start_timestamp, 1)

        format_label = f"MP3 ({bitrate}kbps)" if is_audio else f"Video ({height}p)"

        with tracker_lock:
            download_tracker[download_id].update({
                "status": "completed",
                "percent": 100.0,
                "file_path": final_path,
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
                "file_size_str": format_bytes(file_size_bytes),
                "file_size_bytes": file_size_bytes,
                "timestamp": time_str,
                "duration_sec": f"{elapsed_sec}s",
                "client_ip": client_ip,
                "status": "completed"
            })
            save_persistent_logs(download_history_logs)

    except Exception as e:
        print(f"[-] Download failed for {download_id}:", e)
        elapsed_sec = round(time.time() - start_timestamp, 1)
        with tracker_lock:
            download_tracker[download_id].update({
                "status": "error",
                "error_msg": f"Download failed: {str(e)}"
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
                "error_detail": str(e)
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
        download_name = data.get("download_name", "download.mp4")

    if file_path and os.path.exists(file_path):
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
