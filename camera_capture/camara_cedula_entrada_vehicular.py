"""
Captura de Camera250 (192.168.1.250)
Protocolo: RTSP
Modelo: Dahua
"""

import subprocess
import os
from datetime import datetime
from PIL import Image
from .runtime_helpers import get_ffmpeg_path, format_ffmpeg_error

MIN_VALID_IMAGE_BYTES = 20000


def _build_ffmpeg_cmd(rtsp_url: str, output_file: str, transport: str) -> list[str]:
    """Arma comando ffmpeg para extraer un frame estable desde RTSP."""
    return [
        get_ffmpeg_path(),
        '-rtsp_transport', transport,
        '-i', rtsp_url,
        '-vframes', '1',
        '-q:v', '5',
        '-y',
        output_file,
    ]


def _recortar_imagen_cedula(ruta_imagen: str) -> bool:
    """Recorta márgenes de la imagen de cédula (17% arriba, 20% izquierda)."""
    try:
        img = Image.open(ruta_imagen)
        ancho, alto = img.size

        top = int(alto * 0.17)
        left = int(ancho * 0.2)
        right = ancho
        bottom = alto

        img_recortada = img.crop((left, top, right, bottom))
        img_recortada.save(ruta_imagen, quality=95)
        return True
    except Exception:
        return False


def capture_camera250(output_dir: str = "snapshots_camaras") -> dict:
    """
    Captura foto de Camera250 (cedula entrada vehicular)
    
    Args:
        output_dir: Directorio donde guardar la foto
    
    Returns:
        dict con estado de la captura {'success': bool, 'file': str, 'size': int}
    """
    # Configuración
    ip = "192.168.1.250"
    user = "admin"
    password = "DMT_1990"
    rtsp_url = f"rtsp://{user}:{password}@{ip}:554/"
    
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"camara_cedula_entrada_vehicular_{timestamp}.jpg")
    
    try:
        errors = []
        for transport in ('tcp', 'udp'):
            cmd = _build_ffmpeg_cmd(rtsp_url, output_file, transport)
            result = subprocess.run(cmd, capture_output=True, timeout=15)

            # Validar captura exitosa
            if result.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) >= MIN_VALID_IMAGE_BYTES:
                _recortar_imagen_cedula(output_file)
                file_size = os.path.getsize(output_file)
                return {
                    'success': True,
                    'file': output_file,
                    'size': file_size,
                    'camera': 'Camera250 (Cedula)',
                    'ip': ip
                }

            if os.path.exists(output_file):
                size_bytes = os.path.getsize(output_file)
                errors.append(f"{transport.upper()}: captura invalida (size={size_bytes} bytes)")
            else:
                errors.append(f"{transport.upper()}: {format_ffmpeg_error(result.returncode, result.stderr)}")

            if os.path.exists(output_file):
                os.remove(output_file)

        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camera250 (Cedula)',
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
            'camera': 'Camera250 (Cedula)',
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
            'camera': 'Camera250 (Cedula)',
            'ip': ip,
            'error': str(e)
        }
