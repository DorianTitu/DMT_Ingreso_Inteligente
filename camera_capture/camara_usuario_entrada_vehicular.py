"""
Captura de Camera3 (192.168.1.223)
Protocolo: RTSP
Modelo: Dahua DS-K8003-IME1(B)
"""

import subprocess
import os
from datetime import datetime
from .runtime_helpers import get_ffmpeg_path, format_ffmpeg_error

def capture_camera3(output_dir: str = "snapshots_camaras") -> dict:
    """
    Captura foto de Camera3 (usuario entrada vehicular)
    
    Args:
        output_dir: Directorio donde guardar la foto
    
    Returns:
        dict con estado de la captura {'success': bool, 'file': str, 'size': int}
    """
    # Configuración
    ip = "192.168.1.223"
    user = "admin"
    password = "DMT_1990"
    rtsp_url = f"rtsp://{user}:{password}@{ip}:554/"
    
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"camara_usuario_entrada_vehicular_{timestamp}.jpg")
    
    # Comando ffmpeg para capturar desde RTSP
    cmd = [
        get_ffmpeg_path(),
        '-rtsp_transport', 'tcp',
        '-i', rtsp_url,
        '-vframes', '1',
        '-q:v', '5',
        '-y',
        output_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        
        # Validar captura exitosa
        if result.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            file_size = os.path.getsize(output_file)
            return {
                'success': True,
                'file': output_file,
                'size': file_size,
                'camera': 'Camera3 (Usuario)',
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
                'camera': 'Camera3 (Usuario)',
                'ip': ip,
                'error': format_ffmpeg_error(result.returncode, result.stderr)
            }
    except subprocess.TimeoutExpired:
        if os.path.exists(output_file):
            os.remove(output_file)
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camera3 (Usuario)',
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
            'camera': 'Camera3 (Usuario)',
            'ip': ip,
            'error': str(e)
        }
