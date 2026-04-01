"""
Captura de camara usuario entrada vehicular (192.168.1.224)
Protocolo: HTTP con autenticacion Digest
"""

import os
from datetime import datetime

import requests
from requests.auth import HTTPDigestAuth

SESSION = requests.Session()
SESSION.headers.update({"Connection": "keep-alive"})

def capture_camera3(output_dir: str = "snapshots_camaras") -> dict:
    """
    Captura foto de Camera3 (usuario entrada vehicular)
    
    Args:
        output_dir: Directorio donde guardar la foto
    
    Returns:
        dict con estado de la captura {'success': bool, 'file': str, 'size': int}
    """
    ip = "192.168.1.224"
    user = "admin"
    password = "dmt_2390"
    url = f"http://{ip}/cgi-bin/snapshot.cgi"
    
    # Crear directorio si no existe
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
            with open(output_file, 'wb') as f:
                f.write(response.content)

            file_size = os.path.getsize(output_file)
            return {
                'success': True,
                'file': output_file,
                'size': file_size,
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
        if os.path.exists(output_file):
            os.remove(output_file)
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camara Usuario Entrada Vehicular',
            'ip': ip,
            'error': str(e)
        }
