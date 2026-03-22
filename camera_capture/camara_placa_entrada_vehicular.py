"""
Captura de Camera1 (192.168.1.108)
Protocolo: HTTP con autenticación Digest
Modelo: Dahua DS-K8003-IME1(B)
"""

import subprocess
import os
from datetime import datetime

def capture_camera1(output_dir: str = "snapshots_camaras") -> dict:
    """
    Captura foto de Camera1 (placa entrada vehicular)
    
    Args:
        output_dir: Directorio donde guardar la foto
    
    Returns:
        dict con estado de la captura {'success': bool, 'file': str, 'size': int}
    """
    # Configuración
    ip = "192.168.1.108"
    user = "admin"
    password = "dmt_2390"
    url = f"http://{ip}/cgi-bin/snapshot.cgi"
    
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"camara_placa_entrada_vehicular_{timestamp}.jpg")
    
    # Comando curl con autenticación digest
    cmd = [
        'curl',
        '--digest',
        '-u', f'{user}:{password}',
        '-s',
        '-o', output_file,
        '-w', '%{http_code}',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
        http_code = result.stdout.strip()
        
        # Validar captura exitosa
        if http_code == '200' and os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            file_size = os.path.getsize(output_file)
            return {
                'success': True,
                'file': output_file,
                'size': file_size,
                'camera': 'Camera1 (Placa)',
                'ip': ip
            }
        else:
            # Eliminar archivo si la captura no fue exitosa
            if os.path.exists(output_file):
                os.remove(output_file)
            return {
                'success': False,
                'file': None,
                'size': None,
                'camera': 'Camera1 (Placa)',
                'ip': ip,
                'error': f'HTTP code: {http_code}'
            }
    except subprocess.TimeoutExpired:
        if os.path.exists(output_file):
            os.remove(output_file)
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
