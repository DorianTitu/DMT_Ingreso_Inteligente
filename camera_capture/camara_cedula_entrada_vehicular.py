"""
Captura de camara cedula entrada vehicular (192.168.1.4)
Protocolo: HTTP con autenticacion Digest
"""

import os
import time
from datetime import datetime
from io import BytesIO

import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth

SESSION = requests.Session()
SESSION.headers.update({'Connection': 'keep-alive'})
SESSION.mount('http://', HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0))

CAMERA_IP = '192.168.1.4'
CAMERA_USER = 'admin'
CAMERA_PASSWORD = 'DMT_1990'
SNAPSHOT_URL = f'http://{CAMERA_IP}/cgi-bin/snapshot.cgi'
SNAPSHOT_AUTH = HTTPDigestAuth(CAMERA_USER, CAMERA_PASSWORD)
SNAPSHOT_TIMEOUT = (1.5, 4.0)

# Recorte general de captura vehicular.
# Ajusta estos valores para calibrar el recorte base.
GENERAL_CROP_TOP_PCT = 0.12
GENERAL_CROP_LEFT_PCT = 0.08
GENERAL_CROP_RIGHT_PCT = 0.95
GENERAL_CROP_BOTTOM_PCT = 1.00


def crop_capture_cedula_vehicular_bytes(image_bytes: bytes) -> bytes:
    """Recorta la captura de cédula vehicular antes de entregar la imagen al resto del flujo."""
    with Image.open(BytesIO(image_bytes)) as image:
        width, height = image.size
        top = int(height * GENERAL_CROP_TOP_PCT)
        left = int(width * GENERAL_CROP_LEFT_PCT)
        right = int(width * GENERAL_CROP_RIGHT_PCT)
        bottom = int(height * GENERAL_CROP_BOTTOM_PCT)

        top = max(0, min(height, top))
        left = max(0, min(width, left))
        right = max(0, min(width, right))
        bottom = max(0, min(height, bottom))

        if right <= left:
            right = width
        if bottom <= top:
            bottom = height

        cropped = image.crop((left, top, right, bottom))

    output = BytesIO()
    cropped.save(output, format='JPEG', quality=95)
    return output.getvalue()


def capture_camera250(
    output_dir: str = 'snapshots_camaras',
    save_file: bool = True,
    do_ocr: bool = False,
    draw_boxes: bool = False,
) -> dict:
    """
    Captura foto de camara de cedula entrada vehicular.

    Nota: la camara solo captura imagen. El OCR se procesa fuera de este modulo.
    """
    ip = CAMERA_IP

    output_file = None
    if save_file:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f'camara_cedula_entrada_vehicular_{timestamp}.jpg')

    try:
        capture_started = time.perf_counter()
        response = SESSION.get(
            SNAPSHOT_URL,
            auth=SNAPSHOT_AUTH,
            timeout=SNAPSHOT_TIMEOUT,
            stream=False,
        )
        capture_http_ms = int((time.perf_counter() - capture_started) * 1000)

        if response.status_code == 200 and len(response.content) > 1000:
            crop_started = time.perf_counter()
            image_bytes = crop_capture_cedula_vehicular_bytes(response.content)
            crop_ms = int((time.perf_counter() - crop_started) * 1000)

            save_ms = 0
            if output_file:
                save_started = time.perf_counter()
                with open(output_file, 'wb') as file_handle:
                    file_handle.write(image_bytes)
                save_ms = int((time.perf_counter() - save_started) * 1000)

            return {
                'success': True,
                'file': output_file,
                'size': len(image_bytes),
                'image_bytes': image_bytes,
                'camera': 'Camara Cedula Entrada Vehicular',
                'ip': ip,
                'ocr_data': None,
                'ocr_error': None,
                'timings': {
                    'capture_http_ms': capture_http_ms,
                    'capture_crop_ms': crop_ms,
                    'capture_save_file_ms': save_ms,
                    'capture_method': 'http_snapshot_digest',
                },
            }

        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Cedula Entrada Vehicular',
            'ip': ip,
            'error': f'HTTP code: {response.status_code}',
            'timings': {
                'capture_http_ms': capture_http_ms,
                'capture_method': 'http_snapshot_digest',
            },
        }
    except requests.ConnectTimeout:
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Cedula Entrada Vehicular',
            'ip': ip,
            'error': 'Connection timeout - Camera unreachable',
        }
    except requests.Timeout:
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Cedula Entrada Vehicular',
            'ip': ip,
            'error': 'Timeout',
        }
    except Exception as exc:
        if os.path.exists(output_file):
            os.remove(output_file)
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Cedula Entrada Vehicular',
            'ip': ip,
            'error': str(exc),
        }
