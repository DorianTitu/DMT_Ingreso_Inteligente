"""
OCR para cedula de entrada peatonal.
Separa por completo la logica OCR del modulo de captura de camara.
"""

import re
import time
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from app.services.ocr_cedula_entrada_vehicular import (
    _extract_cedula,
    _extract_name_parts,
    _get_ocr_reader,
    _ocr_lines,
    _preprocess_image_for_ocr,
    _sanitize_apellidos,
    _sanitize_nombres,
)

# Zonas editables en porcentaje (x1, y1, x2, y2).
CROP_ZONE_1_PCT = (0.12, 0.80, 0.40, 0.98)
CROP_ZONE_2_PCT = (0.38, 0.31, 0.70, 0.59)
CROP_ZONE_3_PCT = (0.71, 0.24, 0.99, 0.50)
CROP_ZONE_4_PCT = (0.37, 0.13, 0.65, 0.48)

OCR_CEDULA_ALLOWLIST = '0123456789NUI.NO-'
OCR_NAME_ALLOWLIST = 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜÑabcdefghijklmnopqrstuvwxyzáéíóúüñ'
ZONE_4_OCR_MAX_WIDTH = 360
ZONE_4_OCR_CANVAS_SIZE = 520
ZONE_4_OCR_BATCH_SIZE = 1
ZONE_4_OCR_MIN_SIZE = 18


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


def draw_crop_boxes_on_bytes(image_bytes: bytes, cedula_source: str | None = None) -> tuple[bytes, dict] | tuple[None, None]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            zone_1_px = _rect_pct_to_pixels(img.size, CROP_ZONE_1_PCT)
            zone_2_px = _rect_pct_to_pixels(img.size, CROP_ZONE_2_PCT)
            zone_3_px = _rect_pct_to_pixels(img.size, CROP_ZONE_3_PCT)
            zone_4_px = _rect_pct_to_pixels(img.size, CROP_ZONE_4_PCT)

            if cedula_source == 'crop_zone_1':
                active_zones = {'crop_zone_1', 'crop_zone_4'}
            elif cedula_source == 'crop_zone_3':
                active_zones = {'crop_zone_2', 'crop_zone_3'}
            else:
                active_zones = {'crop_zone_1', 'crop_zone_2', 'crop_zone_3', 'crop_zone_4'}

            draw = img.convert('RGB')
            painter = ImageDraw.Draw(draw)

            if 'crop_zone_1' in active_zones:
                painter.rectangle(zone_1_px, outline=(0, 200, 0) if cedula_source == 'crop_zone_1' else (255, 215, 0), width=5)
            if 'crop_zone_2' in active_zones:
                painter.rectangle(zone_2_px, outline=(0, 200, 0) if cedula_source == 'crop_zone_3' else (255, 215, 0), width=5)
            if 'crop_zone_3' in active_zones:
                painter.rectangle(zone_3_px, outline=(0, 200, 0) if cedula_source == 'crop_zone_3' else (255, 215, 0), width=5)
            if 'crop_zone_4' in active_zones:
                painter.rectangle(zone_4_px, outline=(0, 200, 0) if cedula_source == 'crop_zone_1' else (255, 215, 0), width=5)

            output = BytesIO()
            draw.save(output, format='JPEG', quality=95)
            return output.getvalue(), {
                'crop_zone_1_pct': CROP_ZONE_1_PCT,
                'crop_zone_2_pct': CROP_ZONE_2_PCT,
                'crop_zone_3_pct': CROP_ZONE_3_PCT,
                'crop_zone_4_pct': CROP_ZONE_4_PCT,
                'crop_zone_1_px': zone_1_px,
                'crop_zone_2_px': zone_2_px,
                'crop_zone_3_px': zone_3_px,
                'crop_zone_4_px': zone_4_px,
                'cedula_source': cedula_source,
                'active_zones': sorted(active_zones),
            }
    except Exception:
        return None, None


def _preprocess_zone_4_for_ocr(image: Image.Image) -> np.ndarray:
    width, height = image.size
    if width > ZONE_4_OCR_MAX_WIDTH:
        ratio = ZONE_4_OCR_MAX_WIDTH / float(width)
        image = image.resize((ZONE_4_OCR_MAX_WIDTH, int(height * ratio)), Image.BILINEAR)

    gray = image.convert('L')
    gray = ImageOps.autocontrast(gray)
    return np.array(gray)


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
    return [' '.join(line.split()) for line in lines if ' '.join(line.split())]


def _normalize_header_key(text: str) -> str:
    key = re.sub(r'[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]', ' ', text)
    key = ' '.join(key.split()).upper()
    return key.replace('MOMBRES', 'NOMBRES').replace('N0MBRES', 'NOMBRES').replace('APELLIDOSY', 'APELLIDOS Y')


def _is_peatonal_name_noise(text: str) -> bool:
    key = _normalize_header_key(text)
    if not key:
        return True

    noise_tokens = (
        'APELLIDOS',
        'NOMBRES',
        'NOMBRES Y APELLIDOS',
        'APELLIDOS Y NOMBRES',
        'CEDULA',
        'CIUDADAN',
        'REGISTRO',
        'CONDICION',
        'CONDI',
        'CALLE',
        'NACIONALIDAD',
        'SEXO',
        'NACIMIENTO',
        'DIRECCION',
        'GENERAL',
    )

    for noise in noise_tokens:
        if noise in key:
            return True

    return False


def _extract_ocr_with_zone_fallback(image_bytes: bytes) -> dict:
    started = time.perf_counter()
    with Image.open(BytesIO(image_bytes)) as img:
        zone_1_px = _rect_pct_to_pixels(img.size, CROP_ZONE_1_PCT)
        zone_2_px = _rect_pct_to_pixels(img.size, CROP_ZONE_2_PCT)
        zone_3_px = _rect_pct_to_pixels(img.size, CROP_ZONE_3_PCT)
        zone_4_px = _rect_pct_to_pixels(img.size, CROP_ZONE_4_PCT)

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
            'APELLIDOS',
            'NOMBRES',
            'CEDULA',
            'CIUDADAN',
            'REGISTRO',
            'CONDICION',
            'NACIONALIDAD',
            'SEXO',
            'NACIMIENTO',
            'DIRECCION',
            'GENERAL',
        )
        for noise in noise_keys:
            if noise in key:
                return True
        for noise in noise_keys:
            if len(noise) >= 4 and noise[:4] in key:
                return True
        return False

    def _extract_names_following_pattern(lines: list[str]) -> tuple[str | None, str | None]:
        nombres_idx = -1

        for idx, line in enumerate(lines):
            key = _normalize_header_key(line)
            if nombres_idx < 0 and 'NOMBRES' in key:
                nombres_idx = idx

        if nombres_idx < 0:
            return _extract_name_parts(lines)

        nombres_val = None
        for line in lines[nombres_idx + 1:nombres_idx + 4]:
            key = _normalize_header_key(line)
            if not key:
                continue
            if _is_peatonal_name_noise(line):
                continue
            nombres_val = key
            break

        apellidos_above: list[str] = []
        upper_start = max(0, nombres_idx - 2)
        for line in lines[upper_start:nombres_idx]:
            key = _normalize_header_key(line)
            if not key:
                continue
            if 'NOMBRES' in key or 'APELLIDOS' in key:
                continue
            apellidos_above.append(key)

        apellidos_val = ' '.join(apellidos_above) if apellidos_above else None

        if not apellidos_val and not nombres_val:
            return _extract_name_parts(lines)

        return apellidos_val, nombres_val

    def _extract_cedula_zone_1(lines: list[str]) -> str | None:
        for line in lines:
            key = line.upper()
            match_no = re.search(r'(?:N\s*[O0]|N\.)\D*([0-9]{9}\s*-\s*[0-9])', key)
            if match_no:
                digits = re.sub(r'\D', '', match_no.group(1))
                if len(digits) == 10:
                    return digits

        joined = ' | '.join(lines)
        candidates = re.findall(r'[0-9][0-9\s-]{8,}[0-9]', joined)
        for candidate in candidates:
            digits = re.sub(r'\D', '', candidate)
            if len(digits) == 10:
                return digits

        legacy = _extract_cedula(lines)
        if legacy:
            digits = re.sub(r'\D', '', legacy)
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

        joined = ' | '.join(lines)
        match_nine_digits = re.search(r'\b\d{9}\b', joined)
        if match_nine_digits:
            return match_nine_digits.group(0)

        return None

    def _extract_combined_names(lines: list[str]) -> tuple[str | None, str | None]:
        start_idx = -1
        end_idx = len(lines)

        for idx, line in enumerate(lines):
            key = _clean_words(line)
            if start_idx < 0 and 'APELLIDOS' in key and 'NOMBRES' in key:
                start_idx = idx
                continue
            if start_idx >= 0 and 'LUGAR' in key and 'NACIMIENTO' in key:
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

    def _extract_zone_4_separated_names(lines: list[str]) -> tuple[str | None, str | None]:
        return _extract_names_following_pattern(lines)

    cedula = _extract_cedula_zone_1(zone_1_lines)
    apellidos = None
    nombres = None
    cedula_source = None
    flow_route = None
    zone_4_lines_debug = None

    if cedula:
        cedula_source = 'crop_zone_1'
        flow_route = 'found_in_zone_1'

        zone_4_started = time.perf_counter()
        zone_4_lines = _ocr_lines_zone_4(
            reader,
            _preprocess_zone_4_for_ocr(zone_4_img),
            allowlist=OCR_NAME_ALLOWLIST,
        )
        ocr_steps_ms['zone_4_ms'] = int((time.perf_counter() - zone_4_started) * 1000)
        zone_4_lines_debug = zone_4_lines
        apellidos, nombres = _extract_zone_4_separated_names(zone_4_lines)
    else:
        zone_3_started = time.perf_counter()
        zone_3_lines = _ocr_lines(
            reader,
            _preprocess_image_for_ocr(zone_3_img),
            allowlist='0123456789NUI.NO-'
        )
        ocr_steps_ms['zone_3_ms'] = int((time.perf_counter() - zone_3_started) * 1000)
        cedula = _extract_cedula_zone_3(zone_3_lines)
        if cedula:
            cedula_source = 'crop_zone_3'
            flow_route = 'found_in_zone_3'

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
        'cedula': cedula,
        'nombres': nombres,
        'apellidos': apellidos,
        'cedula_source': cedula_source,
        'flow_route': flow_route,
        'tiempos_ms': {
            'crop_ms': crop_ms,
            'crop_ok': True,
            'ocr_ms': ocr_ms,
            'parse_ms': 0,
            'total_ms': total_ms,
            'cedula_fallback_used': False,
            'ocr_steps_ms': ocr_steps_ms,
        },
        'debug_zone_4_lines': zone_4_lines_debug,
    }


def extract_cedula_data_from_bytes(image_bytes: bytes) -> dict:
    return _extract_ocr_with_zone_fallback(image_bytes)
