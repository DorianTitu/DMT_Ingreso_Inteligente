"""
Captura de Camera3 (192.168.1.223)
Protocolo: RTSP
Modelo: Dahua DS-K8003-IME1(B)
"""

import subprocess
import os
from datetime import datetime
from .runtime_helpers import get_ffmpeg_path, format_ffmpeg_error

CAPTURE_TRANSPORT_ORDER = ('udp', 'tcp')
CAMERA_CHANNEL = 1
CAMERA_SUBTYPE = 0
RTSP_PROBE_SIZE = '32768'
RTSP_ANALYZE_DURATION = '200000'


def _build_ffmpeg_cmd(rtsp_url: str, output_file: str, transport: str) -> list[str]:
    """Arma comando ffmpeg estable para capturar un frame."""
    return [
        get_ffmpeg_path(),
        '-nostdin',
        '-hide_banner',
        '-loglevel', 'error',
        '-probesize', RTSP_PROBE_SIZE,
        '-analyzeduration', RTSP_ANALYZE_DURATION,
        '-rtsp_transport', transport,
        '-i', rtsp_url,
        '-map', '0:v:0',
        '-vf', 'scale=trunc(iw*sar):ih,setsar=1',
        '-vframes', '1',
        '-q:v', '3',
        '-y',
        output_file,
    ]

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
    rtsp_url = (
        f"rtsp://{user}:{password}@{ip}:554/"
        f"cam/realmonitor?channel={CAMERA_CHANNEL}&subtype={CAMERA_SUBTYPE}"
    )
    
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"camara_usuario_entrada_vehicular_{timestamp}.jpg")
    
    try:
        errors = []
        for transport in CAPTURE_TRANSPORT_ORDER:
            cmd = _build_ffmpeg_cmd(rtsp_url, output_file, transport)
            result = subprocess.run(cmd, capture_output=True, timeout=10)

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

            if os.path.exists(output_file):
                size_bytes = os.path.getsize(output_file)
                os.remove(output_file)
                errors.append(f"{transport.upper()}: captura invalida (size={size_bytes} bytes)")
            else:
                errors.append(f"{transport.upper()}: {format_ffmpeg_error(result.returncode, result.stderr)}")

        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camera3 (Usuario)',
            'ip': ip,
            'error': ' | '.join(errors)
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
