"""
Captura de Camera250 (192.168.1.250)
Protocolo: RTSP
Modelo: Dahua
"""

import subprocess
import os
import re
import time
import unicodedata
from datetime import datetime
import numpy as np
from PIL import Image, ImageOps
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
CARD_HEADERS = {
    'APELLIDOS',
    'NOMBRES',
    'APELLIDOS Y NOMBRES',
    'NOMBRES Y APELLIDOS',
    'NACIONALIDAD',
    'FECHA DE NACIMIENTO',
    'LUGAR DE NACIMIENTO',
    'SEXO',
    'AUTODEFINICACION',
    'FECHA DE VENCIMIENTO',
    'CONDICION',
    'CEDULA DE',
    'CIUDADANIA',
}


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


def _normalize_key(text: str) -> str:
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^A-Za-z0-9\s]', ' ', text)
    return _normalize_spaces(text).upper()


def _clean_text_for_name(text: str) -> str:
    cleaned = re.sub(r'[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]', ' ', text)
    return _normalize_spaces(cleaned).upper()


def _is_probable_header(line_key: str) -> bool:
    if not line_key:
        return False
    return any(h in line_key for h in CARD_HEADERS)


def _collect_values_after_header(upper_lines: list[str], start_idx: int, max_items: int = 2) -> list[str]:
    values = []
    for idx in range(start_idx + 1, len(upper_lines)):
        candidate = upper_lines[idx]
        if not candidate:
            continue
        candidate_key = _normalize_key(candidate)
        if _is_probable_header(candidate_key):
            break
        values.append(candidate)
        if len(values) >= max_items:
            break
    return values


def _preprocess_image_for_ocr(image: Image.Image) -> np.ndarray:
    gray = image.convert('L')
    gray = ImageOps.autocontrast(gray)
    return np.array(gray)


def _ocr_lines(reader, image_array: np.ndarray, allowlist: str | None = None) -> list[str]:
    lines = reader.readtext(
        image_array,
        detail=0,
        paragraph=False,
        decoder='greedy',
        beamWidth=1,
        allowlist=allowlist,
    )
    return [_normalize_spaces(line) for line in lines if _normalize_spaces(line)]


def _dedupe_preserve_order(lines: list[str]) -> list[str]:
    seen = set()
    out = []
    for line in lines:
        key = _normalize_key(line)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


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
    """Prioriza cédula por contexto (NUI/No./Documento) y longitud esperada."""
    best_score = -10**9
    best_value = None

    for raw_line in lines:
        line_key = _normalize_key(raw_line)
        for number in re.findall(r'\b\d{8,13}\b', raw_line):
            score = 0
            if len(number) == 10:
                score += 6
            if 'NUI' in line_key:
                score += 6
            if ('NO' in line_key or 'NUM' in line_key or 'DOCUMENTO' in line_key or 'CEDULA' in line_key):
                score += 4
            if ('FECHA' in line_key or 'NACIMIENTO' in line_key or 'VENCIMIENTO' in line_key or 'NAT' in line_key):
                score -= 4

            if score > best_score:
                best_score = score
                best_value = number

    if best_value:
        return best_value

    # Fallback simple: primer candidato encontrado.
    joined = ' '.join(lines)
    fallback = re.findall(r'\b\d{8,13}\b', joined)
    return fallback[0] if fallback else None


def _extract_name_parts(lines: list[str]) -> tuple[str | None, str | None]:
    """Extrae nombres y apellidos considerando dos formatos de cédula ecuatoriana."""
    upper_lines = [_clean_text_for_name(line) for line in lines if line and line.strip()]
    if not upper_lines:
        return None, None

    apellidos = None
    nombres = None

    # Formato 1: APELLIDOS (debajo apellidos) y NOMBRES (debajo nombres).
    for idx, line in enumerate(upper_lines):
        line_key = _normalize_key(line)
        if 'APELLID' in line_key and 'NOMBRES' not in line_key:
            values = _collect_values_after_header(upper_lines, idx, max_items=2)
            if values:
                apellidos = ' '.join(values)
                break

    for idx, line in enumerate(upper_lines):
        line_key = _normalize_key(line)
        if 'NOMBR' in line_key and 'APELLID' not in line_key:
            values = _collect_values_after_header(upper_lines, idx, max_items=2)
            if values:
                nombres = ' '.join(values)
                break

    # Formato 2: APELLIDOS Y NOMBRES (dos líneas: primero apellidos, luego nombres).
    if (not apellidos or not nombres):
        for idx, line in enumerate(upper_lines):
            line_key = _normalize_key(line)
            if ('APELLIDOS Y NOMBRES' in line_key or 'NOMBRES Y APELLIDOS' in line_key):
                values = _collect_values_after_header(upper_lines, idx, max_items=2)
                if values:
                    if not apellidos:
                        apellidos = values[0]
                    if not nombres and len(values) > 1:
                        nombres = values[1]
                break

    return apellidos, nombres


def warmup_cedula_ocr_reader() -> None:
    """Precarga el modelo OCR para reducir latencia de la primera captura."""
    _get_ocr_reader()


def extract_cedula_data_from_image(image_path: str) -> dict:
    """Ejecuta OCR sobre la imagen de cédula y extrae cédula, nombres y apellidos."""
    started = time.perf_counter()
    reader = _get_ocr_reader()
    image = Image.open(image_path)
    width, height = image.size

    # OCR por regiones para acelerar procesamiento.
    info_crop = image.crop((int(width * 0.25), int(height * 0.02), width, height))
    nui_crop = image.crop((0, int(height * 0.75), int(width * 0.62), height))

    info_lines = _ocr_lines(reader, _preprocess_image_for_ocr(info_crop))
    nui_lines = _ocr_lines(reader, _preprocess_image_for_ocr(nui_crop), allowlist='0123456789NUI.NO')

    ocr_finished = time.perf_counter()

    lines = _dedupe_preserve_order(info_lines + nui_lines)
    confidences = []

    if lines:
        confidences = [1.0 for _ in lines]

    cedula = _extract_cedula(lines)
    apellidos, nombres = _extract_name_parts(lines)
    parse_finished = time.perf_counter()

    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else None
    return {
        'cedula': cedula,
        'nombres': nombres,
        'apellidos': apellidos,
        'texto_detectado': lines,
        'confidence_promedio': avg_conf,
        'tiempos_ms': {
            'ocr_ms': int((ocr_finished - started) * 1000),
            'parse_ms': int((parse_finished - ocr_finished) * 1000),
            'total_ms': int((parse_finished - started) * 1000),
        },
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
