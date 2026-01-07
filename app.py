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
        
        if not url.strip():
            return jsonify({'error': 'Invalid URL'}), 400
        
        # Configure yt-dlp options
        filename = f"{int(time.time())}"
        
        # Base options with improved compatibility
        base_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
        
        if download_type == 'audio':
            ydl_opts = {
                **base_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }],
            }
        else:
            # Use format that works better with recent YouTube changes
            if quality == '1080':
                format_string = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
            elif quality == '720':
                format_string = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
            elif quality == '480':
                format_string = 'bestvideo[height<=480]+bestaudio/best[height<=480]/best'
            else:
                format_string = 'bestvideo[height<=360]+bestaudio/best[height<=360]/best'
            
            ydl_opts = {
                **base_opts,
                'format': format_string,
                'merge_output_format': 'mp4',
            }
        
        # Download with better error handling
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First, extract info to validate
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                return jsonify({'error': f'Cannot access video: {str(e)}'}), 400
            
            if info is None:
                return jsonify({'error': 'Could not retrieve video information. The video may be private, unavailable, or age-restricted.'}), 400
            
            # Now download
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:
                return jsonify({'error': f'Download failed: {str(e)}'}), 500
            
            if info is None:
                return jsonify({'error': 'Download failed - could not retrieve video'}), 500
            
            title = info.get('title', 'Unknown')
            
            # Find the downloaded file
            for file in Path(DOWNLOAD_FOLDER).glob(f'{filename}.*'):
                return jsonify({
                    'success': True,
                    'filename': file.name,
                    'title': title,
                    'type': download_type
                })
        
        return jsonify({'error': 'Download completed but file not found'}), 500
        
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if 'player response' in error_msg.lower():
            return jsonify({'error': 'YouTube updated their system. Please update yt-dlp: pip install --upgrade yt-dlp'}), 400
        return jsonify({'error': f'Download error: {error_msg}'}), 400
    except yt_dlp.utils.ExtractorError as e:
        return jsonify({'error': f'Cannot extract video: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/file/<filename>')
def get_file(filename):
    try:
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/files')
def list_files():
    try:
        files = []
        for file in Path(DOWNLOAD_FOLDER).glob('*'):
            if file.is_file():
                files.append({
                    'name': file.name,
                    'size': f"{file.stat().st_size / (1024*1024):.2f} MB",
                    'date': time.ctime(file.stat().st_mtime)
                })
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'success': True, 'message': 'File deleted'})
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)