# app.py
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
from pathlib import Path
import time
import threading

app = Flask(__name__)

# ==============================
# CONFIG
# ==============================
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ==============================
# AUTO CLEANUP THREAD
# ==============================
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            for f in Path(DOWNLOAD_FOLDER).glob("*"):
                if f.is_file() and now - f.stat().st_mtime > 3600:
                    f.unlink()
        except Exception as e:
            print("Cleanup error:", e)
        time.sleep(600)

threading.Thread(target=cleanup_old_files, daemon=True).start()

# ==============================
# ROUTES
# ==============================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    try:
        data = request.get_json()
        url = data.get("url")
        dtype = data.get("type", "video")
        quality = str(data.get("quality", "720"))

        if not url:
            return jsonify({"error": "URL required"}), 400

        filename = str(int(time.time()))

        # ==============================
        # yt-dlp BASE OPTIONS (SAFE)
        # ==============================
        base_opts = {
            "outtmpl": f"{DOWNLOAD_FOLDER}/{filename}.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
            "nocheckcertificate": True,

            # 2026 YouTube compatible
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"]
                }
            },

            # ⭐ BEST FIX (local PC only)
            # Uncomment if Chrome exists
            # "cookiesfrombrowser": ("chrome",),
        }

        # ==============================
        # AUDIO
        # ==============================
        if dtype == "audio":
            ydl_opts = {
                **base_opts,
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }

        # ==============================
        # VIDEO
        # ==============================
        else:
            ydl_opts = {
                **base_opts,
                "format": f"bestvideo[height<={quality}]+bestaudio/best/best",
                "merge_output_format": "mp4",
            }

        # ==============================
        # DOWNLOAD
        # ==============================
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        title = info.get("title", "video")

        # Find file
        for f in Path(DOWNLOAD_FOLDER).glob(f"{filename}.*"):
            return jsonify({
                "success": True,
                "filename": f.name,
                "title": title,
                "type": dtype
            })

        return jsonify({"error": "File not found"}), 500

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "player response" in msg.lower():
            return jsonify({
                "error": "YouTube updated system. Run: pip install -U yt-dlp"
            }), 400
        return jsonify({"error": msg}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/file/<filename>")
def get_file(filename):
    path = os.path.join(DOWNLOAD_FOLDER, filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=True)


@app.route("/files")
def list_files():
    files = []
    for f in Path(DOWNLOAD_FOLDER).glob("*"):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f"{f.stat().st_size / (1024*1024):.2f} MB",
                "date": time.ctime(f.stat().st_mtime)
            })
    return jsonify(files)


@app.route("/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"success": True})
    return jsonify({"error": "File not found"}), 404


# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
