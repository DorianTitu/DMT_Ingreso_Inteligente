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
from PIL import Image, ImageOps, ImageDraw
from .runtime_helpers import get_ffmpeg_path, format_ffmpeg_error

try:
    import easyocr
    OCR_IMPORT_ERROR = None
except Exception as exc:
    easyocr = None
    OCR_IMPORT_ERROR = str(exc)

MIN_VALID_IMAGE_BYTES = 20000
OCR_LANGS = ['es']
_OCR_READER = None
FAST_OCR_MODE = True
OCR_PROFILE = 'ULTRAFAST'
if OCR_PROFILE == 'ULTRAFAST':
    MAX_OCR_IMAGE_WIDTH = 560
    OCR_CANVAS_SIZE = 800
    OCR_BATCH_SIZE = 2
    OCR_MIN_SIZE = 20
    OCR_TEXT_THRESHOLD = 0.55
    OCR_LOW_TEXT = 0.35
    OCR_LINK_THRESHOLD = 0.35
else:
    MAX_OCR_IMAGE_WIDTH = 650
    OCR_CANVAS_SIZE = 960
    OCR_BATCH_SIZE = 4
    OCR_MIN_SIZE = 18
    OCR_TEXT_THRESHOLD = 0.45
    OCR_LOW_TEXT = 0.3
    OCR_LINK_THRESHOLD = 0.3
DRAW_OCR_BOXES = False
INCLUDE_OCR_DEBUG_TEXT = False
CARD_HEADERS = {
    'APELLIDOS',
    'NOMBRES',
    'APELLIDOS Y NOMBRES',
    'NOMBRES Y APELLIDOS'
}
NOISE_NAME_KEYS = {
    'CONDICION',
    'CIUDADANIA',
    'NACIONALIDAD',
    'SEXO',
    'NACIMIENTO',
    'VENCIMIENTO',
}

# Recortes de trabajo para OCR (porcentaje sobre imagen recortada).
# Se usan los dos recortes para extraer nombres/apellidos y cédula.
# Regla de cédula: primero buscar en CROP_ZONE_1_PCT y, si no aparece,
# intentar en CROP_ZONE_2_PCT.
CROP_ZONE_1_PCT = (0.33, 0.33, 0.98, 0.01)
CROP_ZONE_2_PCT = (0.0, 0.80, 0.33, 0.65)


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

        top = int(alto * 0.12)
        left = int(ancho * 0.2)
        right = ancho
        bottom = alto

        img_recortada = img.crop((left, top, right, bottom))
        img_recortada.save(ruta_imagen, quality=95)
        return True
    except Exception:
        return False


def _rect_pct_to_pixels(size: tuple[int, int], rect_pct: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Convierte porcentaje a pixeles y normaliza el rectangulo (x1<x2, y1<y2)."""
    width, height = size
    x1 = int(width * rect_pct[0])
    y1 = int(height * rect_pct[1])
    x2 = int(width * rect_pct[2])
    y2 = int(height * rect_pct[3])

    left = max(0, min(width, min(x1, x2)))
    right = max(0, min(width, max(x1, x2)))
    top = max(0, min(height, min(y1, y2)))
    bottom = max(0, min(height, max(y1, y2)))
    return (left, top, right, bottom)


def _dibujar_cuadros_ocr(ruta_imagen: str, cedula_source: str | None = None) -> dict | None:
    """Dibuja los dos recortes usados por OCR sobre la imagen final."""
    try:
        with Image.open(ruta_imagen) as img:
            zone_1_px = _rect_pct_to_pixels(img.size, CROP_ZONE_1_PCT)
            zone_2_px = _rect_pct_to_pixels(img.size, CROP_ZONE_2_PCT)
            draw = ImageDraw.Draw(img)

            color_1 = (0, 200, 0) if cedula_source == 'crop_zone_1' else (255, 0, 0)
            color_2 = (0, 200, 0) if cedula_source == 'crop_zone_2' else (255, 0, 0)
            draw.rectangle(zone_1_px, outline=color_1, width=5)
            draw.rectangle(zone_2_px, outline=color_2, width=5)

            img.save(ruta_imagen, quality=95)
            return {
                'crop_zone_1_px': zone_1_px,
                'crop_zone_2_px': zone_2_px,
                'cedula_source': cedula_source,
            }
    except Exception:
        return None


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


def _sanitize_nombres(nombres: str | None) -> str | None:
    """Limita nombres a maximo 2 palabras y descarta NACIONALIDAD."""
    if not nombres:
        return None

    tokens = []
    for token in _normalize_spaces(nombres).split(' '):
        key = _normalize_key(token)
        if not key or key in NOISE_NAME_KEYS:
            continue
        tokens.append(token)

    if not tokens:
        return None

    return ' '.join(tokens[:2])


def _sanitize_apellidos(apellidos: str | None) -> str | None:
    """Limpia ruido no util en apellidos (ej. CONDICION CIUDADANIA)."""
    if not apellidos:
        return None

    tokens = []
    for token in _normalize_spaces(apellidos).split(' '):
        key = _normalize_key(token)
        if not key or key in NOISE_NAME_KEYS:
            continue
        tokens.append(token)

    return ' '.join(tokens) if tokens else None


def _is_noise_name_line(text: str) -> bool:
    line_key = _normalize_key(text)
    if not line_key:
        return True
    return any(noise in line_key for noise in NOISE_NAME_KEYS)


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
        if _is_noise_name_line(candidate):
            continue
        values.append(candidate)
        if len(values) >= max_items:
            break
    return values


def _preprocess_image_for_ocr(image: Image.Image) -> np.ndarray:
    # Reduccion agresiva para OCR rapido en CPU.
    width, height = image.size
    if FAST_OCR_MODE and width > MAX_OCR_IMAGE_WIDTH:
        ratio = MAX_OCR_IMAGE_WIDTH / float(width)
        image = image.resize((MAX_OCR_IMAGE_WIDTH, int(height * ratio)), Image.BILINEAR)

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
        batch_size=OCR_BATCH_SIZE,
        workers=0,
        min_size=OCR_MIN_SIZE,
        text_threshold=OCR_TEXT_THRESHOLD,
        low_text=OCR_LOW_TEXT,
        link_threshold=OCR_LINK_THRESHOLD,
        canvas_size=OCR_CANVAS_SIZE,
        mag_ratio=1.0,
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
        try:
            import torch
            cpu_count = os.cpu_count() or 8
            # Usa casi todos los hilos lógicos para maximizar throughput en CPU.
            torch.set_num_threads(max(2, cpu_count - 1))
            torch.set_num_interop_threads(1)
        except Exception:
            pass

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
    upper_lines = [
        _clean_text_for_name(line)
        for line in lines
        if line and line.strip() and not _is_noise_name_line(line)
    ]
    if not upper_lines:
        return None, None

    apellidos = None
    nombres = None
    combined_name_field = any(
        ('APELLIDOS Y NOMBRES' in _normalize_key(line) or 'NOMBRES Y APELLIDOS' in _normalize_key(line))
        for line in upper_lines
    )
    has_separated_nombres_field = any(
        ('NOMBR' in _normalize_key(line) and 'APELLID' not in _normalize_key(line))
        for line in upper_lines
    )

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

    crop_zone_1_px = _rect_pct_to_pixels((width, height), CROP_ZONE_1_PCT)
    crop_zone_2_px = _rect_pct_to_pixels((width, height), CROP_ZONE_2_PCT)

    crop_zone_1 = image.crop(crop_zone_1_px)
    crop_zone_2 = image.crop(crop_zone_2_px)

    # Una sola lectura pesada para nombres/apellidos (zona 1).
    zone_1_lines = _ocr_lines(reader, _preprocess_image_for_ocr(crop_zone_1))

    # Cedula: primero intenta con la lectura general de zona 1.
    cedula = _extract_cedula(zone_1_lines)

    cedula_source = 'crop_zone_1'
    if not cedula:
        # Solo si falla, hace una pasada enfocada para cédula en zona 2.
        zone_2_cedula_lines = _ocr_lines(
            reader,
            _preprocess_image_for_ocr(crop_zone_2),
            allowlist='0123456789NUI.NO'
        )
        cedula = _extract_cedula(zone_2_cedula_lines)
        cedula_source = 'crop_zone_2'

    ocr_finished = time.perf_counter()

    apellidos, nombres = _extract_name_parts(zone_1_lines)
    apellidos = _sanitize_apellidos(apellidos)
    nombres = _sanitize_nombres(nombres)

    parse_finished = time.perf_counter()

    result = {
        'cedula': cedula,
        'nombres': nombres,
        'apellidos': apellidos,
        'cedula_source': cedula_source,
        'tiempos_ms': {
            'ocr_ms': int((ocr_finished - started) * 1000),
            'parse_ms': int((parse_finished - ocr_finished) * 1000),
            'total_ms': int((parse_finished - started) * 1000),
            'cedula_fallback_used': cedula_source == 'crop_zone_2',
        },
    }

    if INCLUDE_OCR_DEBUG_TEXT:
        result['texto_detectado'] = zone_1_lines

    return result


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
    overall_started = time.perf_counter()
    
    try:
        errors = []
        for transport in ('tcp', 'udp'):
            capture_started = time.perf_counter()
            cmd = _build_ffmpeg_cmd(rtsp_url, output_file, transport)
            result = subprocess.run(cmd, capture_output=True, timeout=15)

            # Validar captura exitosa
            if result.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) >= MIN_VALID_IMAGE_BYTES:
                crop_started = time.perf_counter()
                crop_ok = _recortar_imagen_cedula(output_file)
                crop_ms = int((time.perf_counter() - crop_started) * 1000)
                file_size = os.path.getsize(output_file)
                capture_ms = int((time.perf_counter() - capture_started) * 1000)

                ocr_data = None
                ocr_error = None
                ocr_ms = None
                try:
                    ocr_data = extract_cedula_data_from_image(output_file)
                    if ocr_data and isinstance(ocr_data.get('tiempos_ms'), dict):
                        ocr_ms = ocr_data['tiempos_ms'].get('ocr_ms')
                except Exception as ocr_exc:
                    ocr_error = str(ocr_exc)

                ocr_boxes_preview = None
                if DRAW_OCR_BOXES:
                    ocr_boxes_preview = _dibujar_cuadros_ocr(
                        output_file,
                        ocr_data.get('cedula_source') if isinstance(ocr_data, dict) else None,
                    )

                total_pipeline_ms = int((time.perf_counter() - overall_started) * 1000)

                return {
                    'success': True,
                    'file': output_file,
                    'size': file_size,
                    'camera': 'Camera250 (Cedula)',
                    'ip': ip,
                    'ocr_data': ocr_data,
                    'ocr_error': ocr_error,
                    'timings': {
                        'capture_ms': capture_ms,
                        'crop_ms': crop_ms,
                        'crop_ok': crop_ok,
                        'ocr_ms': ocr_ms,
                        'total_pipeline_ms': total_pipeline_ms,
                    }
                }

                if ocr_boxes_preview is not None:
                    response['ocr_boxes_preview'] = ocr_boxes_preview

                return response

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
