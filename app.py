# app.py
from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import os
from pathlib import Path
import time
import threading

app = Flask(__name__)

# Create downloads folder
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Clean up old files (older than 1 hour)
def cleanup_old_files():
    while True:
        try:
            current_time = time.time()
            for file in Path(DOWNLOAD_FOLDER).glob('*'):
                if current_time - file.stat().st_mtime > 3600:  # 1 hour
                    file.unlink()
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(600)  # Run every 10 minutes

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.json
        url = data.get('url')
        download_type = data.get('type', 'video')
        quality = data.get('quality', '720')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Configure yt-dlp options
        filename = f"{int(time.time())}"
        
        if download_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }],
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        else:
            ydl_opts = {
                'format': f'best[height<={quality}]',
                'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        
        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown')
            
            # Find the downloaded file
            for file in Path(DOWNLOAD_FOLDER).glob(f'{filename}.*'):
                return jsonify({
                    'success': True,
                    'filename': file.name,
                    'title': title,
                    'type': download_type
                })
        
        return jsonify({'error': 'Download failed'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/file/<filename>')
def get_file(filename):
    try:
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/files')
def list_files():
    try:
        files = []
        for file in Path(DOWNLOAD_FOLDER).glob('*'):
            files.append({
                'name': file.name,
                'size': f"{file.stat().st_size / (1024*1024):.2f} MB",
                'date': time.ctime(file.stat().st_mtime)
            })
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)