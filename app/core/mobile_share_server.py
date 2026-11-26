"""
Local Wi-Fi Mobile Share Server for Vidroa (PromptBeast).
Runs a lightweight local web server on port 10246 and generates a QR code
so users can scan with their phone and download ONLY the rendered MP4 file
to their mobile photo library/camera roll.
"""

import os
import socket
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Tuple


def get_local_ip() -> str:
    """Returns local LAN IP address e.g. 192.168.1.15."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MobileShareServer:
    """Hosts a single rendered video file for 1-click mobile download over local Wi-Fi."""

    _server: Optional[HTTPServer] = None
    _thread: Optional[threading.Thread] = None
    _video_path: Optional[str] = None
    _port: int = 10246

    @classmethod
    def start(cls, video_path: str, port: int = 10246) -> Tuple[str, str]:
        """
        Starts local server if not already running and returns (share_url, qr_data_url).
        Serves ONLY the target video file (no directory listing or sibling file access).
        """
        cls.stop()
        target_p = Path(video_path).resolve()
        cls._video_path = str(target_p)
        cls._port = port

        file_name = target_p.name
        encoded_name = urllib.parse.quote(file_name)
        allowed_video_paths = {f"/{encoded_name}", f"/{file_name}", "/video"}

        class VideoShareHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                clean_path = self.path.split("?", 1)[0]
                if clean_path in ("/", "/download"):
                    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Vidroa Video Download</title>
    <style>
        body {{ background: #0b0f19; color: #f8fafc; font-family: -apple-system, sans-serif; text-align: center; padding: 30px; }}
        .card {{ background: #121c2d; border-radius: 16px; padding: 24px; max-width: 400px; margin: 0 auto; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        h2 {{ color: #10b981; margin-top: 0; }}
        a.btn {{ display: block; background: #10b981; color: white; padding: 14px 24px; text-decoration: none; border-radius: 10px; font-weight: bold; margin-top: 20px; font-size: 16px; }}
        video {{ width: 100%; border-radius: 10px; margin-top: 15px; background: #000; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>⚡ Vidroa Video Ready</h2>
        <p>{file_name}</p>
        <video controls playsinline src="/{encoded_name}"></video>
        <a class="btn" href="/{encoded_name}" download="{file_name}">📥 Save Video to Camera Roll</a>
    </div>
</body>
</html>"""
                    body = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif clean_path in allowed_video_paths and target_p.exists() and target_p.is_file():
                    file_size = target_p.stat().st_size
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Content-Disposition", f'attachment; filename="{file_name}"')
                    self.end_headers()
                    with open(target_p, "rb") as vf:
                        while True:
                            chunk = vf.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                else:
                    self.send_error(404, "Not Found")

            def log_message(self, format, *args):
                pass

        try:
            cls._server = HTTPServer(("0.0.0.0", cls._port), VideoShareHandler)
            cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
            cls._thread.start()
        except Exception as e:
            print(f"Notice: Share server start: {e}")

        local_ip = get_local_ip()
        share_url = f"http://{local_ip}:{cls._port}/"
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(share_url)}"
        return share_url, qr_url

    @classmethod
    def stop(cls):
        """Stops the active share server."""
        if cls._server:
            try:
                cls._server.shutdown()
                cls._server.server_close()
            except Exception:
                pass
            cls._server = None
        cls._thread = None
        cls._video_path = None
