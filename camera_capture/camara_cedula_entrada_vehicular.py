"""
Captura de Camera250 (192.168.1.250)
Protocolo: RTSP
Modelo: Dahua
"""

import subprocess
import os
import re
from datetime import datetime
from PIL import Image
from .runtime_helpers import get_ffmpeg_path, format_ffmpeg_error

try:
    import easyocr
    OCR_IMPORT_ERROR = None
except Exception as exc:
    easyocr = None
    OCR_IMPORT_ERROR = str(exc)

MIN_VALID_IMAGE_BYTES = 20000
OCR_LANGS = ['es', 'en']
_OCR_READER = None


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


def _normalize_spaces(text: str) -> str:
    return ' '.join(text.split())


def _clean_text_for_name(text: str) -> str:
    cleaned = re.sub(r'[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]', ' ', text)
    return _normalize_spaces(cleaned).upper()


def _get_ocr_reader():
    """Crea (una sola vez) el lector EasyOCR."""
    global _OCR_READER
    if easyocr is None:
        if OCR_IMPORT_ERROR:
            raise RuntimeError(f'EasyOCR no disponible: {OCR_IMPORT_ERROR}')
        raise RuntimeError('EasyOCR no está instalado. Ejecuta: pip install -r requirements.txt')

    if _OCR_READER is None:
        _OCR_READER = easyocr.Reader(OCR_LANGS, gpu=False)
    return _OCR_READER


def _extract_cedula(lines: list[str]) -> str | None:
    """Busca una cédula probable como secuencia de 8-13 dígitos."""
    joined = ' '.join(lines)
    candidates = re.findall(r'\b\d{8,13}\b', joined)
    return candidates[0] if candidates else None


def _extract_name_parts(lines: list[str]) -> tuple[str | None, str | None]:
    """Intenta extraer apellidos y nombres de líneas OCR con patrones típicos de cédula."""
    upper_lines = [_clean_text_for_name(line) for line in lines if line and line.strip()]
    if not upper_lines:
        return None, None

    apellidos = None
    nombres = None

    for idx, line in enumerate(upper_lines):
        if 'APELLID' in line and idx + 1 < len(upper_lines):
            next_line = upper_lines[idx + 1]
            if len(next_line.split()) >= 1:
                apellidos = next_line
                break

    for idx, line in enumerate(upper_lines):
        if 'NOMBR' in line and idx + 1 < len(upper_lines):
            next_line = upper_lines[idx + 1]
            if len(next_line.split()) >= 1:
                nombres = next_line
                break

    if (not apellidos or not nombres):
        for idx, line in enumerate(upper_lines):
            if ('APELLIDOS Y NOMBRES' in line or 'NOMBRES Y APELLIDOS' in line) and idx + 1 < len(upper_lines):
                full_name = upper_lines[idx + 1]
                tokens = full_name.split()
                if len(tokens) >= 4:
                    if not apellidos:
                        apellidos = ' '.join(tokens[:2])
                    if not nombres:
                        nombres = ' '.join(tokens[2:])
                elif len(tokens) >= 2:
                    if not apellidos:
                        apellidos = tokens[0]
                    if not nombres:
                        nombres = ' '.join(tokens[1:])
                break

    return apellidos, nombres


def extract_cedula_data_from_image(image_path: str) -> dict:
    """Ejecuta OCR sobre la imagen de cédula y extrae cédula, nombres y apellidos."""
    reader = _get_ocr_reader()
    ocr_raw = reader.readtext(image_path, detail=1)

    lines = []
    confidences = []
    for _, text, confidence in ocr_raw:
        normalized = _normalize_spaces(text)
        if normalized:
            lines.append(normalized)
            confidences.append(float(confidence))

    cedula = _extract_cedula(lines)
    apellidos, nombres = _extract_name_parts(lines)

    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else None
    return {
        'cedula': cedula,
        'nombres': nombres,
        'apellidos': apellidos,
        'texto_detectado': lines,
        'confidence_promedio': avg_conf,
    }


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

                ocr_data = None
                ocr_error = None
                try:
                    ocr_data = extract_cedula_data_from_image(output_file)
                except Exception as ocr_exc:
                    ocr_error = str(ocr_exc)

                return {
                    'success': True,
                    'file': output_file,
                    'size': file_size,
                    'camera': 'Camera250 (Cedula)',
                    'ip': ip,
                    'ocr_data': ocr_data,
                    'ocr_error': ocr_error,
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
