"""
OCR de cedulas (vehicular y peatonal) separado de los modulos de camara.
"""

from abc import ABC, abstractmethod
from io import BytesIO
import os
import re
import time
import unicodedata

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

CARD_HEADERS = {
    'APELLIDOS',
    'NOMBRES',
    'APELLIDOS Y NOMBRES',
    'NOMBRES Y APELLIDOS',
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

# Recortes vehicular (4 zonas propias, distintas a peatonal)
VEHICULAR_CROP_ZONE_1_PCT = (0.05, 0.82, 0.32, 0.95)
VEHICULAR_CROP_ZONE_2_PCT = (0.30, 0.25, 0.65, 0.55)
VEHICULAR_CROP_ZONE_3_PCT = (0.65, 0.20, 0.98, 0.40)
VEHICULAR_CROP_ZONE_4_PCT = (0.31, 0.12, 0.67, 0.45)

# Recortes peatonal
PEATONAL_CROP_ZONE_1_PCT = (0.10, 0.80, 0.45, 0.98)
PEATONAL_CROP_ZONE_2_PCT = (0.38, 0.31, 0.70, 0.59)
PEATONAL_CROP_ZONE_3_PCT = (0.71, 0.24, 0.99, 0.50)
PEATONAL_CROP_ZONE_4_PCT = (0.37, 0.13, 0.65, 0.48)

OCR_CEDULA_ALLOWLIST = '0123456789NUI.NO-'
OCR_NAME_ALLOWLIST = 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜÑabcdefghijklmnopqrstuvwxyzáéíóúüñ'
ZONE_4_OCR_MAX_WIDTH = 360
ZONE_4_OCR_CANVAS_SIZE = 520
ZONE_4_OCR_BATCH_SIZE = 1
ZONE_4_OCR_MIN_SIZE = 18


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


def _preprocess_image_for_ocr(image: Image.Image) -> np.ndarray:
    width, height = image.size
    if FAST_OCR_MODE and width > MAX_OCR_IMAGE_WIDTH:
        ratio = MAX_OCR_IMAGE_WIDTH / float(width)
        image = image.resize((MAX_OCR_IMAGE_WIDTH, int(height * ratio)), Image.BILINEAR)

    gray = image.convert('L')
    gray = ImageOps.autocontrast(gray)
    return np.array(gray)


def _preprocess_zone_4_for_ocr(image: Image.Image) -> np.ndarray:
    width, height = image.size
    if width > ZONE_4_OCR_MAX_WIDTH:
        ratio = ZONE_4_OCR_MAX_WIDTH / float(width)
        image = image.resize((ZONE_4_OCR_MAX_WIDTH, int(height * ratio)), Image.BILINEAR)

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


def _ocr_lines_zone_4(reader, image_array: np.ndarray, allowlist: str | None = None) -> list[str]:
    lines = reader.readtext(
        image_array,
        detail=0,
        paragraph=False,
        decoder='greedy',
        beamWidth=1,
        batch_size=ZONE_4_OCR_BATCH_SIZE,
        workers=0,
        min_size=ZONE_4_OCR_MIN_SIZE,
        text_threshold=0.60,
        low_text=0.40,
        link_threshold=0.40,
        canvas_size=ZONE_4_OCR_CANVAS_SIZE,
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


def warmup_cedula_ocr_reader() -> None:
    _get_ocr_reader()


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


def _extract_cedula_vehicular_from_pil(image: Image.Image) -> dict:
    started = time.perf_counter()

    crop_started = time.perf_counter()
    width, height = image.size
    top = int(height * 0.12)
    left = int(width * 0.2)
    image = image.crop((left, top, width, height))
    crop_finished = time.perf_counter()

    reader = _get_ocr_reader()
    width, height = image.size
    crop_zone_1_px = _rect_pct_to_pixels((width, height), VEHICULAR_CROP_ZONE_1_PCT)
    crop_zone_2_px = _rect_pct_to_pixels((width, height), VEHICULAR_CROP_ZONE_2_PCT)

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
            allowlist='0123456789NUI.NO',
        )
        cedula = _extract_cedula(zone_2_cedula_lines)
        cedula_source = 'crop_zone_2'

    ocr_finished = time.perf_counter()

    apellidos, nombres = _extract_name_parts(zone_1_lines)
    apellidos = _sanitize_apellidos(apellidos)
    nombres = _sanitize_nombres(nombres)

    parse_finished = time.perf_counter()

    return {
        'cedula': cedula,
        'nombres': nombres,
        'apellidos': apellidos,
        'cedula_source': cedula_source,
        'tiempos_ms': {
            'crop_ms': int((crop_finished - crop_started) * 1000),
            'crop_ok': True,
            'ocr_ms': int((ocr_finished - ocr_started) * 1000),
            'parse_ms': int((parse_finished - ocr_finished) * 1000),
            'total_ms': int((parse_finished - started) * 1000),
            'cedula_fallback_used': cedula_source == 'crop_zone_2',
        },
    }


def extract_cedula_vehicular_from_bytes(image_bytes: bytes) -> dict:
    with Image.open(BytesIO(image_bytes)) as image:
        return _extract_cedula_vehicular_from_pil(image.copy())


def draw_vehicular_crop_boxes(image_bytes: bytes, cedula_source: str | None = None) -> tuple[bytes, dict] | tuple[None, None]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            width, height = img.size
            base_top = int(height * 0.12)
            base_left = int(width * 0.2)
            base_right = width
            base_bottom = height
            base_crop_px = (base_left, base_top, base_right, base_bottom)

            cropped_width = max(1, base_right - base_left)
            cropped_height = max(1, base_bottom - base_top)

            zone_1_local = _rect_pct_to_pixels((cropped_width, cropped_height), VEHICULAR_CROP_ZONE_1_PCT)
            zone_2_local = _rect_pct_to_pixels((cropped_width, cropped_height), VEHICULAR_CROP_ZONE_2_PCT)

            zone_1_px = (
                base_left + zone_1_local[0],
                base_top + zone_1_local[1],
                base_left + zone_1_local[2],
                base_top + zone_1_local[3],
            )
            zone_2_px = (
                base_left + zone_2_local[0],
                base_top + zone_2_local[1],
                base_left + zone_2_local[2],
                base_top + zone_2_local[3],
            )

            draw = ImageDraw.Draw(img)
            draw.rectangle(base_crop_px, outline=(255, 215, 0), width=5)
            color_1 = (0, 200, 0) if cedula_source == 'crop_zone_1' else (255, 0, 0)
            color_2 = (0, 200, 0) if cedula_source == 'crop_zone_2' else (255, 0, 0)
            draw.rectangle(zone_1_px, outline=color_1, width=5)
            draw.rectangle(zone_2_px, outline=color_2, width=5)

            output = BytesIO()
            img.save(output, format='JPEG', quality=95)
            return output.getvalue(), {
                'base_crop_px': base_crop_px,
                'crop_zone_1_px': zone_1_px,
                'crop_zone_2_px': zone_2_px,
                'cedula_source': cedula_source,
            }
    except Exception:
        return None, None


def extract_cedula_peatonal_from_bytes(image_bytes: bytes) -> dict:
    started = time.perf_counter()
    with Image.open(BytesIO(image_bytes)) as img:
        zone_1_px = _rect_pct_to_pixels(img.size, PEATONAL_CROP_ZONE_1_PCT)
        zone_2_px = _rect_pct_to_pixels(img.size, PEATONAL_CROP_ZONE_2_PCT)
        zone_3_px = _rect_pct_to_pixels(img.size, PEATONAL_CROP_ZONE_3_PCT)
        zone_4_px = _rect_pct_to_pixels(img.size, PEATONAL_CROP_ZONE_4_PCT)

        crop_started = time.perf_counter()
        zone_1_img = img.crop(zone_1_px)
        zone_2_img = img.crop(zone_2_px)
        zone_3_img = img.crop(zone_3_px)
        zone_4_img = img.crop(zone_4_px)
        crop_ms = int((time.perf_counter() - crop_started) * 1000)

    reader = _get_ocr_reader()
    ocr_started = time.perf_counter()
    ocr_steps_ms: dict[str, int] = {}

    zone_1_started = time.perf_counter()
    zone_1_lines = _ocr_lines(
        reader,
        _preprocess_image_for_ocr(zone_1_img),
        allowlist=OCR_CEDULA_ALLOWLIST,
    )
    ocr_steps_ms['zone_1_ms'] = int((time.perf_counter() - zone_1_started) * 1000)

    def _clean_words(line: str) -> str:
        cleaned = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]", " ", line)
        return " ".join(cleaned.split()).upper()

    def _is_name_noise_or_header(line: str) -> bool:
        key = _clean_words(line)
        if not key:
            return True
        noise_keys = (
            "APELLIDOS",
            "NOMBRES",
            "CEDULA",
            "CIUDADAN",
            "REGISTRO",
            "CONDICION",
            "NACIONALIDAD",
            "SEXO",
            "NACIMIENTO",
            "DIRECCION",
            "GENERAL",
        )
        for noise in noise_keys:
            if noise in key:
                return True

        for noise in noise_keys:
            if len(noise) >= 4:
                prefix = noise[:4]
                if prefix in key:
                    return True

        return False

    def _extract_names_following_pattern(lines: list[str]) -> tuple[str | None, str | None]:
        nombres_idx = -1

        for idx, line in enumerate(lines):
            key = _clean_words(line)
            if nombres_idx < 0 and "NOMBRES" in key:
                nombres_idx = idx

        if nombres_idx < 0:
            return _extract_name_parts(lines)

        nombres_val = None
        for line in lines[nombres_idx + 1:]:
            key = _clean_words(line)
            if not key:
                continue
            if _is_name_noise_or_header(line):
                continue
            nombres_val = key
            break

        apellidos_above: list[str] = []
        for line in reversed(lines[:nombres_idx]):
            key = _clean_words(line)
            if not key or _is_name_noise_or_header(line):
                continue
            apellidos_above.append(key)
            if len(apellidos_above) == 2:
                break
        apellidos_above.reverse()

        apellidos_val = " ".join(apellidos_above) if apellidos_above else None

        if not apellidos_val and not nombres_val:
            return _extract_name_parts(lines)

        return apellidos_val, nombres_val

    def _extract_cedula_zone_1(lines: list[str]) -> str | None:
        for line in lines:
            key = line.upper()
            match_no = re.search(r"(?:N\s*[O0]|N\.)\D*([0-9]{9}\s*-\s*[0-9])", key)
            if match_no:
                digits = re.sub(r"\D", "", match_no.group(1))
                if len(digits) == 10:
                    return digits

        joined = " | ".join(lines)
        candidates = re.findall(r"[0-9][0-9\s-]{8,}[0-9]", joined)
        for candidate in candidates:
            digits = re.sub(r"\D", "", candidate)
            if len(digits) == 10:
                return digits

        legacy = _extract_cedula(lines)
        if legacy:
            digits = re.sub(r"\D", "", legacy)
            if len(digits) == 10:
                return digits
        return None

    def _extract_cedula_zone_3(lines: list[str]) -> str | None:
        cedula = _extract_cedula_zone_1(lines)
        if cedula:
            return cedula

        cedula = _extract_cedula(lines)
        if cedula:
            return cedula

        joined = " | ".join(lines)
        match_nine_digits = re.search(r"\b\d{9}\b", joined)
        if match_nine_digits:
            return match_nine_digits.group(0)

        return None

    def _extract_combined_names(lines: list[str]) -> tuple[str | None, str | None]:
        start_idx = -1
        end_idx = len(lines)

        for idx, line in enumerate(lines):
            key = _clean_words(line)
            if start_idx < 0 and "APELLIDOS" in key and "NOMBRES" in key:
                start_idx = idx
                continue
            if start_idx >= 0 and "LUGAR" in key and "NACIMIENTO" in key:
                end_idx = idx
                break

        if start_idx < 0:
            return _extract_names_following_pattern(lines)

        candidates: list[str] = []
        for line in lines[start_idx + 1:end_idx]:
            cleaned = _clean_words(line)
            if not cleaned:
                continue
            if _is_name_noise_or_header(cleaned):
                continue
            candidates.append(cleaned)
            if len(candidates) >= 2:
                break

        if len(candidates) >= 2:
            return candidates[0], candidates[1]

        return _extract_names_following_pattern(lines)

    cedula = _extract_cedula_zone_1(zone_1_lines)
    apellidos = None
    nombres = None
    cedula_source = None
    flow_route = None
    zone_4_lines_debug = None

    if cedula:
        cedula_source = "crop_zone_1"
        flow_route = "found_in_zone_1"

        zone_4_started = time.perf_counter()
        zone_4_lines = _ocr_lines_zone_4(
            reader,
            _preprocess_zone_4_for_ocr(zone_4_img),
            allowlist=OCR_NAME_ALLOWLIST,
        )
        ocr_steps_ms['zone_4_ms'] = int((time.perf_counter() - zone_4_started) * 1000)
        zone_4_lines_debug = zone_4_lines
        apellidos, nombres = _extract_names_following_pattern(zone_4_lines)
    else:
        zone_3_started = time.perf_counter()
        zone_3_lines = _ocr_lines(
            reader,
            _preprocess_image_for_ocr(zone_3_img),
            allowlist='0123456789NUI.NO-',
        )
        ocr_steps_ms['zone_3_ms'] = int((time.perf_counter() - zone_3_started) * 1000)
        cedula = _extract_cedula_zone_3(zone_3_lines)
        if cedula:
            cedula_source = "crop_zone_3"
            flow_route = "found_in_zone_3"

        zone_2_started = time.perf_counter()
        zone_2_lines = _ocr_lines(
            reader,
            _preprocess_image_for_ocr(zone_2_img),
            allowlist=OCR_NAME_ALLOWLIST,
        )
        ocr_steps_ms['zone_2_ms'] = int((time.perf_counter() - zone_2_started) * 1000)
        apellidos, nombres = _extract_combined_names(zone_2_lines)

    apellidos = _sanitize_apellidos(apellidos)
    nombres = _sanitize_nombres(nombres)

    ocr_ms = int((time.perf_counter() - ocr_started) * 1000)
    total_ms = int((time.perf_counter() - started) * 1000)

    return {
        "cedula": cedula,
        "nombres": nombres,
        "apellidos": apellidos,
        "cedula_source": cedula_source,
        "flow_route": flow_route,
        "tiempos_ms": {
            "crop_ms": crop_ms,
            "crop_ok": True,
            "ocr_ms": ocr_ms,
            "parse_ms": 0,
            "total_ms": total_ms,
            "cedula_fallback_used": False,
            'ocr_steps_ms': ocr_steps_ms,
        },
        "debug_zone_4_lines": zone_4_lines_debug,
    }


def extract_cedula_vehicular_4zones_from_bytes(image_bytes: bytes) -> dict:
    """Ejecuta la misma logica OCR de 4 recortes usando zonas vehiculares propias."""
    global PEATONAL_CROP_ZONE_1_PCT, PEATONAL_CROP_ZONE_2_PCT, PEATONAL_CROP_ZONE_3_PCT, PEATONAL_CROP_ZONE_4_PCT

    original_zones = (
        PEATONAL_CROP_ZONE_1_PCT,
        PEATONAL_CROP_ZONE_2_PCT,
        PEATONAL_CROP_ZONE_3_PCT,
        PEATONAL_CROP_ZONE_4_PCT,
    )
    try:
        PEATONAL_CROP_ZONE_1_PCT = VEHICULAR_CROP_ZONE_1_PCT
        PEATONAL_CROP_ZONE_2_PCT = VEHICULAR_CROP_ZONE_2_PCT
        PEATONAL_CROP_ZONE_3_PCT = VEHICULAR_CROP_ZONE_3_PCT
        PEATONAL_CROP_ZONE_4_PCT = VEHICULAR_CROP_ZONE_4_PCT
        return extract_cedula_peatonal_from_bytes(image_bytes)
    finally:
        (
            PEATONAL_CROP_ZONE_1_PCT,
            PEATONAL_CROP_ZONE_2_PCT,
            PEATONAL_CROP_ZONE_3_PCT,
            PEATONAL_CROP_ZONE_4_PCT,
        ) = original_zones


def draw_peatonal_crop_boxes(
    image_bytes: bytes,
    route: str | None = None,
) -> tuple[bytes, dict] | tuple[None, None]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            zone_1_px = _rect_pct_to_pixels(img.size, PEATONAL_CROP_ZONE_1_PCT)
            zone_2_px = _rect_pct_to_pixels(img.size, PEATONAL_CROP_ZONE_2_PCT)
            zone_3_px = _rect_pct_to_pixels(img.size, PEATONAL_CROP_ZONE_3_PCT)
            zone_4_px = _rect_pct_to_pixels(img.size, PEATONAL_CROP_ZONE_4_PCT)

            draw = ImageDraw.Draw(img)
            if route == "found_in_zone_1":
                active_zones = {"crop_zone_1", "crop_zone_4"}
                draw.rectangle(zone_1_px, outline=(0, 200, 0), width=5)
                draw.rectangle(zone_4_px, outline=(0, 200, 0), width=5)
            elif route == "found_in_zone_3":
                active_zones = {"crop_zone_2", "crop_zone_3"}
                draw.rectangle(zone_2_px, outline=(0, 200, 0), width=5)
                draw.rectangle(zone_3_px, outline=(0, 200, 0), width=5)
            else:
                active_zones = set()
                draw.rectangle(zone_1_px, outline=(255, 0, 0), width=5)
                draw.rectangle(zone_2_px, outline=(255, 0, 0), width=5)
                draw.rectangle(zone_3_px, outline=(255, 0, 0), width=5)
                draw.rectangle(zone_4_px, outline=(255, 0, 0), width=5)

            output = BytesIO()
            img.save(output, format='JPEG', quality=95)
            return output.getvalue(), {
                "crop_zone_1_pct": PEATONAL_CROP_ZONE_1_PCT,
                "crop_zone_2_pct": PEATONAL_CROP_ZONE_2_PCT,
                "crop_zone_3_pct": PEATONAL_CROP_ZONE_3_PCT,
                "crop_zone_4_pct": PEATONAL_CROP_ZONE_4_PCT,
                "crop_zone_1_px": zone_1_px,
                "crop_zone_2_px": zone_2_px,
                "crop_zone_3_px": zone_3_px,
                "crop_zone_4_px": zone_4_px,
                "flow_route": route,
                "active_zones": sorted(active_zones),
            }
    except Exception:
        return None, None


def draw_vehicular_4zones_crop_boxes(
    image_bytes: bytes,
    route: str | None = None,
) -> tuple[bytes, dict] | tuple[None, None]:
    """Dibuja cajas de los 4 recortes vehiculares propios."""
    global PEATONAL_CROP_ZONE_1_PCT, PEATONAL_CROP_ZONE_2_PCT, PEATONAL_CROP_ZONE_3_PCT, PEATONAL_CROP_ZONE_4_PCT

    original_zones = (
        PEATONAL_CROP_ZONE_1_PCT,
        PEATONAL_CROP_ZONE_2_PCT,
        PEATONAL_CROP_ZONE_3_PCT,
        PEATONAL_CROP_ZONE_4_PCT,
    )
    try:
        PEATONAL_CROP_ZONE_1_PCT = VEHICULAR_CROP_ZONE_1_PCT
        PEATONAL_CROP_ZONE_2_PCT = VEHICULAR_CROP_ZONE_2_PCT
        PEATONAL_CROP_ZONE_3_PCT = VEHICULAR_CROP_ZONE_3_PCT
        PEATONAL_CROP_ZONE_4_PCT = VEHICULAR_CROP_ZONE_4_PCT
        return draw_peatonal_crop_boxes(image_bytes, route)
    finally:
        (
            PEATONAL_CROP_ZONE_1_PCT,
            PEATONAL_CROP_ZONE_2_PCT,
            PEATONAL_CROP_ZONE_3_PCT,
            PEATONAL_CROP_ZONE_4_PCT,
        ) = original_zones


class GenericCedulaOCR(ABC):
    """Contrato base para analizadores OCR de cédula."""

    def warmup(self) -> None:
        warmup_cedula_ocr_reader()

    @abstractmethod
    def analyze(self, image_bytes: bytes) -> dict:
        raise NotImplementedError

    def draw_boxes(
        self,
        image_bytes: bytes,
        analysis: dict | None = None,
    ) -> tuple[bytes | None, dict | None]:
        return None, None


class CedulaVehicularOCR(GenericCedulaOCR):
    """Implementación OCR para cédula vehicular."""

    def analyze(self, image_bytes: bytes) -> dict:
        return extract_cedula_vehicular_4zones_from_bytes(image_bytes)

    def draw_boxes(
        self,
        image_bytes: bytes,
        analysis: dict | None = None,
    ) -> tuple[bytes | None, dict | None]:
        route = analysis.get('flow_route') if isinstance(analysis, dict) else None
        boxed, meta = draw_vehicular_4zones_crop_boxes(image_bytes, route)
        return boxed, meta


class CedulaPeatonalOCR(GenericCedulaOCR):
    """Implementación OCR para cédula peatonal."""

    def analyze(self, image_bytes: bytes) -> dict:
        return extract_cedula_peatonal_from_bytes(image_bytes)

    def draw_boxes(
        self,
        image_bytes: bytes,
        analysis: dict | None = None,
    ) -> tuple[bytes | None, dict | None]:
        route = analysis.get('flow_route') if isinstance(analysis, dict) else None
        boxed, meta = draw_peatonal_crop_boxes(image_bytes, route)
        return boxed, meta


_VEHICULAR_OCR = CedulaVehicularOCR()
_PEATONAL_OCR = CedulaPeatonalOCR()


def get_vehicular_ocr() -> CedulaVehicularOCR:
    return _VEHICULAR_OCR


def get_peatonal_ocr() -> CedulaPeatonalOCR:
    return _PEATONAL_OCR
