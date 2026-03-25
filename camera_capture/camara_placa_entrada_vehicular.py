"""
Captura de Camera1 (192.168.1.108)
Protocolo: HTTP con autenticación Digest
Modelo: Dahua DS-K8003-IME1(B)
"""

import os
from datetime import datetime
from requests.auth import HTTPDigestAuth
import requests

def capture_camera1(output_dir: str = "snapshots_camaras") -> dict:
    """
    Captura foto de Camera1 (placa entrada vehicular)
    
    Args:
        output_dir: Directorio donde guardar la foto
    
    Returns:
        dict con estado de la captura {'success': bool, 'file': str, 'size': int}
    """
    # Configuración
    ip = "192.168.1.2"
    user = "admin"
    password = "DMT_1990"
    url = f"http://{ip}/cgi-bin/snapshot.cgi"
    
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"camara_placa_entrada_vehicular_{timestamp}.jpg")
    
    try:
        # Usar requests con autenticación Digest
        response = requests.get(
            url,
            auth=HTTPDigestAuth(user, password),
            timeout=10,
            stream=True
        )
        
        # Validar captura exitosa
        if response.status_code == 200 and len(response.content) > 1000:
            # Guardar imagen
            with open(output_file, 'wb') as f:
                f.write(response.content)
            
            file_size = os.path.getsize(output_file)
            return {
                'success': True,
                'file': output_file,
                'size': file_size,
                'camera': 'Camera1 (Placa)',
                'ip': ip
            }
        else:
            return {
                'success': False,
                'file': None,
                'size': None,
                'camera': 'Camera1 (Placa)',
                'ip': ip,
                'error': f'HTTP code: {response.status_code}'
            }
    except requests.ConnectTimeout:
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camera1 (Placa)',
            'ip': ip,
            'error': 'Connection timeout - Camera unreachable'
        }
    except requests.Timeout:
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camera1 (Placa)',
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
            'camera': 'Camera1 (Placa)',
            'ip': ip,
            'error': str(e)
        }
