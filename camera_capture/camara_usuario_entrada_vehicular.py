"""
Captura de camara usuario entrada vehicular (192.168.1.223)
Protocolo: HTTP Digest con fallback RTSP
"""

import os
from datetime import datetime

import cv2
import requests
from requests.auth import HTTPDigestAuth

SESSION = requests.Session()
SESSION.headers.update({"Connection": "keep-alive"})


def _capture_from_rtsp(ip: str, user: str, password: str):
    """Obtiene un frame por RTSP usando rutas comunes de Dahua."""
    rtsp_urls = [
        f"rtsp://{user}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0",
        f"rtsp://{user}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=1",
        f"rtsp://{user}:{password}@{ip}:554/live/ch00_0",
        f"rtsp://{user}:{password}@{ip}:554/live/ch01_0",
        f"rtsp://{user}:{password}@{ip}:554/Streaming/Channels/101",
    ]

    for url in rtsp_urls:
        cap = cv2.VideoCapture(url)
        try:
            if not cap.isOpened():
                continue

            ok, frame = cap.read()
            if not ok or frame is None or frame.size == 0:
                continue

            encode_ok, encoded = cv2.imencode('.jpg', frame)
            if not encode_ok:
                continue

            return encoded.tobytes(), url
        finally:
            cap.release()

    return None, None

def capture_camera3(output_dir: str = "snapshots_camaras", save_file: bool = True) -> dict:
    """
    Captura foto de Camera3 (usuario entrada vehicular)
    
    Args:
        output_dir: Directorio donde guardar la foto
    
    Returns:
        dict con estado de la captura {'success': bool, 'file': str, 'size': int}
    """
    ip = "192.168.1.224"
    user = "admin"
    password = "DMT_1990"
    url = f"http://{ip}/cgi-bin/snapshot.cgi"
    
    output_file = None
    if save_file:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"camara_usuario_entrada_vehicular_{timestamp}.jpg")
    try:
        response = SESSION.get(
            url,
            auth=HTTPDigestAuth(user, password),
            timeout=(2, 6),
            stream=False,
        )

        if response.status_code == 200 and len(response.content) > 1000:
            image_bytes = response.content
            if output_file:
                with open(output_file, 'wb') as f:
                    f.write(image_bytes)

            file_size = len(image_bytes)
            return {
                'success': True,
                'file': output_file,
                'size': file_size,
                'image_bytes': image_bytes,
                'capture_method': 'http_snapshot',
                'camera': 'Camara Usuario Entrada Vehicular',
                'ip': ip
            }

        # Fallback RTSP cuando snapshot HTTP no esta disponible (ej. 404)
        image_bytes, rtsp_url = _capture_from_rtsp(ip, user, password)
        if image_bytes and len(image_bytes) > 1000:
            if output_file:
                with open(output_file, 'wb') as f:
                    f.write(image_bytes)

            file_size = len(image_bytes)
            return {
                'success': True,
                'file': output_file,
                'size': file_size,
                'image_bytes': image_bytes,
                'capture_method': 'rtsp_frame',
                'rtsp_url': rtsp_url,
                'camera': 'Camara Usuario Entrada Vehicular',
                'ip': ip
            }

        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Usuario Entrada Vehicular',
            'ip': ip,
            'error': f'HTTP code: {response.status_code}'
        }
    except requests.ConnectTimeout:
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Usuario Entrada Vehicular',
            'ip': ip,
            'error': 'Connection timeout - Camera unreachable'
        }
    except requests.Timeout:
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Usuario Entrada Vehicular',
            'ip': ip,
            'error': 'Timeout'
        }
    except Exception as e:
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Usuario Entrada Vehicular',
            'ip': ip,
            'error': str(e)
        }
