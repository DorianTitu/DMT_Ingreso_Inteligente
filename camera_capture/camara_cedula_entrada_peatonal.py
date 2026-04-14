"""
Captura de camara de cedula entrada peatonal (192.168.1.3)
Protocolo: HTTP con autenticacion Digest
"""

import os
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth

SESSION = requests.Session()
SESSION.headers.update({'Connection': 'keep-alive'})
SESSION.mount('http://', HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0))

CAMERA_IP = '192.168.1.3'
CAMERA_USER = 'admin'
CAMERA_PASSWORD = 'DMT_1990'
SNAPSHOT_URL = f'http://{CAMERA_IP}/cgi-bin/snapshot.cgi'
SNAPSHOT_AUTH = HTTPDigestAuth(CAMERA_USER, CAMERA_PASSWORD)
SNAPSHOT_TIMEOUT = (1.5, 4.0)


def capture_cedula_entrada_peatonal(
    output_dir: str = 'snapshots_camaras',
    save_file: bool = True,
) -> dict:
    """Captura foto de la camara de cedula entrada peatonal y retorna solo captura."""
    ip = CAMERA_IP

    output_file = None
    if save_file:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f'camara_cedula_entrada_peatonal_{timestamp}.jpg')

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
            image_bytes = response.content
            if output_file:
                with open(output_file, 'wb') as file:
                    file.write(image_bytes)

            file_size = len(image_bytes)
            return {
                'success': True,
                'file': output_file,
                'size': file_size,
                'image_bytes': image_bytes,
                'camera': 'Camara Cedula Entrada Peatonal',
                'ip': ip,
                'timings': {
                    'capture_http_ms': capture_http_ms,
                    'capture_method': 'http_snapshot_digest',
                },
            }

        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Cedula Entrada Peatonal',
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
            'camera': 'Camara Cedula Entrada Peatonal',
            'ip': ip,
            'error': 'Connection timeout - Camera unreachable',
        }
    except requests.Timeout:
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Cedula Entrada Peatonal',
            'ip': ip,
            'error': 'Timeout',
        }
    except Exception as exc:
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Cedula Entrada Peatonal',
            'ip': ip,
            'error': str(exc),
        }
