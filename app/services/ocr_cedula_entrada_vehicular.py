"""
OCR para cedula de entrada vehicular.
Separa por completo la logica OCR del modulo de captura de camara.
"""

import os
import re
import time
import unicodedata
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageOps

try:
    import easyocr
    OCR_IMPORT_ERROR = None
except Exception as exc:
    easyocr = None
    OCR_IMPORT_ERROR = str(exc)

OCR_LANGS = ['es']
_OCR_READER = None
FAST_OCR_MODE = True
OCR_PROFILE = 'ULTRAFAST'
if OCR_PROFILE == 'ULTRAFAST':
    MAX_OCR_IMAGE_WIDTH = 500
    OCR_CANVAS_SIZE = 700
    OCR_BATCH_SIZE = 2
    OCR_MIN_SIZE = 20
    OCR_TEXT_THRESHOLD = 0.60
    OCR_LOW_TEXT = 0.40
    OCR_LINK_THRESHOLD = 0.40
else:
    MAX_OCR_IMAGE_WIDTH = 650
    OCR_CANVAS_SIZE = 960
    OCR_BATCH_SIZE = 4
    OCR_MIN_SIZE = 18
    OCR_TEXT_THRESHOLD = 0.45
    OCR_LOW_TEXT = 0.3
    OCR_LINK_THRESHOLD = 0.3

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
NOISE_NAME_PREFIXES = (
    'CONDICI',
    'CIUDADA',
    'NACIONA',
    'NACIMI',
    'VENCIMI',
)

# Recortes de trabajo para OCR (porcentaje sobre imagen recortada).
CROP_ZONE_1_PCT = (0.33, 0.33, 0.98, 0.01)
CROP_ZONE_2_PCT = (0.0, 0.80, 0.33, 0.65)


def _rect_pct_to_pixels(size: tuple[int, int], rect_pct: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
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


def _build_ocr_boxes_metadata(size: tuple[int, int], cedula_source: str | None = None) -> dict:
    width, height = size
    zone_1_px = _rect_pct_to_pixels((width, height), CROP_ZONE_1_PCT)
    zone_2_px = _rect_pct_to_pixels((width, height), CROP_ZONE_2_PCT)
    return {
        'base_crop_px': (0, 0, width, height),
        'crop_zone_1_px': zone_1_px,
        'crop_zone_2_px': zone_2_px,
        'cedula_source': cedula_source,
    }


def draw_ocr_boxes_on_bytes(image_bytes: bytes, cedula_source: str | None = None) -> tuple[bytes, dict] | tuple[None, None]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            metadata = _build_ocr_boxes_metadata(img.size, cedula_source)
            draw = ImageDraw.Draw(img)
            draw.rectangle(metadata['base_crop_px'], outline=(255, 215, 0), width=5)
            color_1 = (0, 200, 0) if cedula_source == 'crop_zone_1' else (255, 0, 0)
            color_2 = (0, 200, 0) if cedula_source == 'crop_zone_2' else (255, 0, 0)
            draw.rectangle(metadata['crop_zone_1_px'], outline=color_1, width=5)
            draw.rectangle(metadata['crop_zone_2_px'], outline=color_2, width=5)

            output = BytesIO()
            img.save(output, format='JPEG', quality=95)
            return output.getvalue(), metadata
    except Exception:
        return None, None


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
    if not nombres:
        return None

    tokens = []
    for token in _normalize_spaces(nombres).split(' '):
        key = _normalize_key(token)
        if not key:
            continue
        if key in NOISE_NAME_KEYS or any(key.startswith(prefix) for prefix in NOISE_NAME_PREFIXES):
            continue
        tokens.append(token)

    if not tokens:
        return None

    return ' '.join(tokens[:2])


def _sanitize_apellidos(apellidos: str | None) -> str | None:
    if not apellidos:
        return None

    tokens = []
    for token in _normalize_spaces(apellidos).split(' '):
        key = _normalize_key(token)
        if not key:
            continue
        if key in NOISE_NAME_KEYS or any(key.startswith(prefix) for prefix in NOISE_NAME_PREFIXES):
            continue
        tokens.append(token)

    return ' '.join(tokens) if tokens else None


def _is_noise_name_line(text: str) -> bool:
    line_key = _normalize_key(text)
    if not line_key:
        return True
    if any(noise in line_key for noise in NOISE_NAME_KEYS):
        return True
    return any(prefix in line_key for prefix in NOISE_NAME_PREFIXES)


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


def _get_ocr_reader():
    global _OCR_READER
    if easyocr is None:
        if OCR_IMPORT_ERROR:
            raise RuntimeError(f'EasyOCR no disponible: {OCR_IMPORT_ERROR}')
        raise RuntimeError('EasyOCR no esta instalado. Ejecuta: pip install -r requirements.txt')

    if _OCR_READER is None:
        try:
            import torch
            cpu_count = os.cpu_count() or 8
            torch.set_num_threads(max(2, min(6, cpu_count - 1)))
            torch.set_num_interop_threads(1)
        except Exception:
            pass

        _OCR_READER = easyocr.Reader(OCR_LANGS, gpu=False)
    return _OCR_READER


def _extract_cedula(lines: list[str]) -> str | None:
    best_score = -10**9
    best_value = None

    for raw_line in lines:
        line_key = _normalize_key(raw_line)
        candidates = re.findall(r'\b\d{8,13}(?:\s*-\s*\d)?\b', raw_line)
        for number in candidates:
            digits_only = re.sub(r'\D', '', number)
            score = 0
            if len(digits_only) == 10:
                score += 6
            if 'NUI' in line_key:
                score += 6
            if ('NO' in line_key or 'NUM' in line_key or 'DOCUMENTO' in line_key or 'CEDULA' in line_key):
                score += 4
            if ('FECHA' in line_key or 'NACIMIENTO' in line_key or 'VENCIMIENTO' in line_key or 'NAT' in line_key):
                score -= 4

            if score > best_score:
                best_score = score
                best_value = digits_only

    if best_value:
        return best_value

    joined = ' '.join(lines)
    fallback = re.findall(r'\b\d{8,13}(?:\s*-\s*\d)?\b', joined)
    return re.sub(r'\D', '', fallback[0]) if fallback else None


def _extract_name_parts(lines: list[str]) -> tuple[str | None, str | None]:
    upper_lines = [
        _clean_text_for_name(line)
        for line in lines
        if line and line.strip() and not _is_noise_name_line(line)
    ]
    if not upper_lines:
        return None, None

    apellidos = None
    nombres = None

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

    if not apellidos or not nombres:
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
    _get_ocr_reader()


def extract_cedula_data_from_pil(image: Image.Image) -> dict:
    started = time.perf_counter()
    crop_started = time.perf_counter()
    try:
        crop_ok = True
    except Exception:
        crop_ok = False
    crop_finished = time.perf_counter()

    reader = _get_ocr_reader()
    width, height = image.size

    crop_zone_1_px = _rect_pct_to_pixels((width, height), CROP_ZONE_1_PCT)
    crop_zone_2_px = _rect_pct_to_pixels((width, height), CROP_ZONE_2_PCT)

    crop_zone_1 = image.crop(crop_zone_1_px)
    crop_zone_2 = image.crop(crop_zone_2_px)

    ocr_started = time.perf_counter()
    zone_1_lines = _ocr_lines(reader, _preprocess_image_for_ocr(crop_zone_1))
    cedula = _extract_cedula(zone_1_lines)

    cedula_source = 'crop_zone_1'
    if not cedula:
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
            'crop_ms': int((crop_finished - crop_started) * 1000),
            'crop_ok': crop_ok,
            'ocr_ms': int((ocr_finished - ocr_started) * 1000),
            'parse_ms': int((parse_finished - ocr_finished) * 1000),
            'total_ms': int((parse_finished - started) * 1000),
            'cedula_fallback_used': cedula_source == 'crop_zone_2',
        },
    }

    if INCLUDE_OCR_DEBUG_TEXT:
        result['texto_detectado'] = zone_1_lines

    return result


def extract_cedula_data_from_image(image_path: str) -> dict:
    with Image.open(image_path) as image:
        return extract_cedula_data_from_pil(image.copy())


def extract_cedula_data_from_bytes(image_bytes: bytes) -> dict:
    with Image.open(BytesIO(image_bytes)) as image:
        return extract_cedula_data_from_pil(image.copy())
