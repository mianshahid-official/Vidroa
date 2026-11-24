"""
Local Wi-Fi Mobile Share Server for PromptBeast.
Runs a lightweight local web server on port 10246 and generates a QR code
so users can scan with their phone and download the rendered MP4 directly
to their mobile photo library/camera roll.
"""

import os
import socket
import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
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
    """Hosts rendered videos for 1-click mobile download over local Wi-Fi."""

    _server: Optional[HTTPServer] = None
    _thread: Optional[threading.Thread] = None
    _video_path: Optional[str] = None
    _port: int = 10246

    @classmethod
    def start(cls, video_path: str, port: int = 10246) -> Tuple[str, str]:
        """
        Starts local server if not already running and returns (share_url, qr_data_url).
        """
        cls.stop()
        cls._video_path = str(Path(video_path).resolve())
        cls._port = port

        file_dir = str(Path(cls._video_path).parent)
        file_name = Path(cls._video_path).name

        class VideoShareHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=file_dir, **kwargs)

            def do_GET(self):
                if self.path == "/" or self.path == "/download":
                    # Serve friendly HTML landing page
                    encoded_name = urllib.parse.quote(file_name)
                    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PromptBeast Video Download</title>
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
        <h2>⚡ PromptBeast Video Ready</h2>
        <p>{file_name}</p>
        <video controls playsinline src="/{encoded_name}"></video>
        <a class="btn" href="/{encoded_name}" download>📥 Save Video to Camera Roll</a>
    </div>
</body>
</html>"""
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html.encode("utf-8"))))
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                else:
                    super().do_GET()

        try:
            cls._server = HTTPServer(("0.0.0.0", cls._port), VideoShareHandler)
            cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
            cls._thread.start()
        except Exception as e:
            print(f"Notice: Share server start: {e}")

        local_ip = get_local_ip()
        share_url = f"http://{local_ip}:{cls._port}/"
        # QR Code generator URL (or clean SVG)
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
