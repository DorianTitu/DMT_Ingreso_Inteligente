"""
Captura de camara de cedula entrada peatonal (192.168.1.3)
Protocolo: HTTP con autenticacion Digest
"""

import os
from io import BytesIO
from datetime import datetime
import time
import re
import numpy as np

import requests
from PIL import Image, ImageDraw, ImageOps
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth
from .camara_cedula_entrada_vehicular import (
    _extract_cedula,
    _extract_name_parts,
    _get_ocr_reader,
    _ocr_lines,
    _preprocess_image_for_ocr,
    _sanitize_apellidos,
    _sanitize_nombres,
)

SESSION = requests.Session()
SESSION.headers.update({"Connection": "keep-alive"})
SESSION.mount("http://", HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0))

CAMERA_IP = "192.168.1.3"
CAMERA_USER = "admin"
CAMERA_PASSWORD = "DMT_1990"
SNAPSHOT_URL = f"http://{CAMERA_IP}/cgi-bin/snapshot.cgi"
SNAPSHOT_AUTH = HTTPDigestAuth(CAMERA_USER, CAMERA_PASSWORD)
SNAPSHOT_TIMEOUT = (1.5, 4.0)

# Zonas editables en porcentaje (x1, y1, x2, y2) para ajustar recortes visualmente.
CROP_ZONE_1_PCT = (0.12, 0.80, 0.40, 0.98) #Zona de la cedula nueva
CROP_ZONE_2_PCT = (0.38, 0.31, 0.70, 0.59) #Zona de nombre y apellido cedula antigua
CROP_ZONE_3_PCT = (0.71, 0.24, 0.99, 0.50) #Zona de la cedula antigua
CROP_ZONE_4_PCT = (0.37, 0.13, 0.65, 0.48) #Zona de la cedula nueva



DRAW_CROP_BOXES = True
BOX_WIDTH = 5
ENABLE_PRECISE_NAME_FALLBACK = True


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


def _draw_crop_boxes(image_bytes: bytes, cedula_source: str | None = None) -> tuple[bytes, dict] | tuple[None, None]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            zone_1_px = _rect_pct_to_pixels(img.size, CROP_ZONE_1_PCT)
            zone_2_px = _rect_pct_to_pixels(img.size, CROP_ZONE_2_PCT)
            zone_3_px = _rect_pct_to_pixels(img.size, CROP_ZONE_3_PCT)
            zone_4_px = _rect_pct_to_pixels(img.size, CROP_ZONE_4_PCT)

            draw = ImageDraw.Draw(img)
            if cedula_source == "found_in_zone_1":
                active_zones = {"crop_zone_1", "crop_zone_4"}
                draw.rectangle(zone_1_px, outline=(0, 200, 0), width=BOX_WIDTH)
                draw.rectangle(zone_4_px, outline=(0, 200, 0), width=BOX_WIDTH)
            elif cedula_source == "not_found_in_zone_1":
                active_zones = {"crop_zone_2", "crop_zone_3"}
                draw.rectangle(zone_2_px, outline=(0, 200, 0), width=BOX_WIDTH)
                draw.rectangle(zone_3_px, outline=(0, 200, 0), width=BOX_WIDTH)
            else:
                output = BytesIO()
                img.save(output, format="JPEG", quality=95)
                return output.getvalue(), {
                    "crop_zone_1_pct": CROP_ZONE_1_PCT,
                    "crop_zone_2_pct": CROP_ZONE_2_PCT,
                    "crop_zone_3_pct": CROP_ZONE_3_PCT,
                    "crop_zone_4_pct": CROP_ZONE_4_PCT,
                    "crop_zone_1_px": zone_1_px,
                    "crop_zone_2_px": zone_2_px,
                    "crop_zone_3_px": zone_3_px,
                    "crop_zone_4_px": zone_4_px,
                    "cedula_source": cedula_source,
                    "active_zones": [],
                }

            output = BytesIO()
            img.save(output, format="JPEG", quality=95)
            return output.getvalue(), {
                "crop_zone_1_pct": CROP_ZONE_1_PCT,
                "crop_zone_2_pct": CROP_ZONE_2_PCT,
                "crop_zone_3_pct": CROP_ZONE_3_PCT,
                "crop_zone_4_pct": CROP_ZONE_4_PCT,
                "crop_zone_1_px": zone_1_px,
                "crop_zone_2_px": zone_2_px,
                "crop_zone_3_px": zone_3_px,
                "crop_zone_4_px": zone_4_px,
                "cedula_source": cedula_source,
                "active_zones": sorted(active_zones),
            }
    except Exception:
        return None, None


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

    # OCR de zona 1 para primer intento de cedula.
    zone_1_lines = _ocr_lines(reader, _preprocess_image_for_ocr(zone_1_img))

    def _clean_words(line: str) -> str:
        cleaned = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]", " ", line)
        return " ".join(cleaned.split()).upper()

    def _ocr_lines_precise(reader_obj, image_obj: Image.Image, allowlist: str | None = None) -> list[str]:
        # Segundo barrido mas preciso: conserva mas detalle y baja umbral de deteccion.
        width, height = image_obj.size
        upscale = 1.5 if max(width, height) < 550 else 1.2
        resized = image_obj.resize(
            (int(width * upscale), int(height * upscale)),
            Image.BICUBIC,
        )
        gray = ImageOps.autocontrast(resized.convert("L"))
        arr = np.array(gray)
        lines = reader_obj.readtext(
            arr,
            detail=0,
            paragraph=False,
            decoder='beamsearch',
            beamWidth=5,
            batch_size=1,
            workers=0,
            min_size=10,
            text_threshold=0.45,
            low_text=0.25,
            link_threshold=0.25,
            canvas_size=1200,
            mag_ratio=1.2,
            allowlist=allowlist,
        )
        return [" ".join(str(line).split()) for line in lines if " ".join(str(line).split())]

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
        # Verificación exacta de substring
        for noise in noise_keys:
            if noise in key:
                return True
        
        # Verificación robusta ante OCR parcial: detecta prefijos de 4+ caracteres
        # Captura variantes parciales como: COND, NACI, REGI, CIUDA, NACION, etc.
        for noise in noise_keys:
            if len(noise) >= 4:
                prefix = noise[:4]
                if prefix in key:
                    return True
        
        return False

    def _extract_names_following_pattern(lines: list[str]) -> tuple[str | None, str | None]:
        """
        Regla de mapeo simplificada:
        - Debajo de NOMBRES: nombres.
        - Las dos líneas válidas inmediatamente encima de NOMBRES: apellidos.
        """
        nombres_idx = -1

        for idx, line in enumerate(lines):
            key = _clean_words(line)
            if nombres_idx < 0 and "NOMBRES" in key:
                nombres_idx = idx

        if nombres_idx < 0:
            return _extract_name_parts(lines)

        # 1) NOMBRES: primera línea válida debajo del header NOMBRES.
        nombres_val = None
        for line in lines[nombres_idx + 1:]:
            key = _clean_words(line)
            if not key:
                continue
            if _is_name_noise_or_header(line):
                continue
            nombres_val = key
            break

        # 2) APELLIDOS: las dos líneas válidas inmediatamente encima de NOMBRES,
        #    descartando ruido (CONDICION, APELLIDOS, REGISTRO, etc.)
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
        # Prioriza patrones tipo "No. 172193122-6" y normaliza sin guion.
        for line in lines:
            key = line.upper()
            match_no = re.search(r"(?:N\s*[O0]|N\.)\D*([0-9]{9}\s*-\s*[0-9])", key)
            if match_no:
                digits = re.sub(r"\D", "", match_no.group(1))
                if len(digits) == 10:
                    return digits

        # Fallback: cualquier bloque de 10 digitos en zona 1 (con o sin guion/espacios).
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

        # Zona 3 puede perder el verificador o el guion en OCR; acepta el bloque de 9 dígitos
        # como último recurso para no devolver null cuando la cédula es visible en la imagen.
        joined = " | ".join(lines)
        match_nine_digits = re.search(r"\b\d{9}\b", joined)
        if match_nine_digits:
            return match_nine_digits.group(0)

        return None

    def _extract_combined_names(lines: list[str]) -> tuple[str | None, str | None]:
        # Patron cedula antigua:
        # APELLIDOS Y NOMBRES
        # <linea apellidos>
        # <linea nombres>
        # ...
        # LUGAR DE NACIMIENTO
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

        # Si no completa el patron del recorte 2, usa fallback general.
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
        cedula_source = "crop_zone_1"
        flow_route = "found_in_zone_1"

        # Si la cedula esta en el recorte 1, los nombres salen separados en el recorte 4.
        zone_4_lines = _ocr_lines(reader, _preprocess_image_for_ocr(zone_4_img))
        zone_4_lines_debug = zone_4_lines
        apellidos, nombres = _extract_zone_4_separated_names(zone_4_lines)
        if ENABLE_PRECISE_NAME_FALLBACK and (not apellidos or not nombres):
            zone_4_lines_precise = _ocr_lines_precise(reader, zone_4_img)
            apellidos_p, nombres_p = _extract_zone_4_separated_names(zone_4_lines_precise)
            apellidos = apellidos or apellidos_p
            nombres = nombres or nombres_p
    else:
        # Si no aparece en el recorte 1, se busca la cedula en el recorte 3
        # y los nombres/apellidos en el recorte 2.
        zone_3_lines = _ocr_lines(
            reader,
            _preprocess_image_for_ocr(zone_3_img),
            allowlist='0123456789NUI.NO-'
        )
        cedula = _extract_cedula_zone_3(zone_3_lines)
        if cedula:
            cedula_source = "crop_zone_3"
            flow_route = "found_in_zone_3"

        zone_2_lines = _ocr_lines(reader, _preprocess_image_for_ocr(zone_2_img))
        apellidos, nombres = _extract_combined_names(zone_2_lines)
        if ENABLE_PRECISE_NAME_FALLBACK and (not apellidos or not nombres):
            zone_2_lines_precise = _ocr_lines_precise(reader, zone_2_img)
            apellidos_p, nombres_p = _extract_combined_names(zone_2_lines_precise)
            apellidos = apellidos or apellidos_p
            nombres = nombres or nombres_p

    apellidos = _sanitize_apellidos(apellidos)
    nombres = _sanitize_nombres(nombres)

    ocr_ms = int((time.perf_counter() - ocr_started) * 1000)
    total_ms = int((time.perf_counter() - started) * 1000)

    result = {
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
        },
        "debug_zone_4_lines": zone_4_lines_debug,
    }
    
    return result


def capture_cedula_entrada_peatonal(
    output_dir: str = "snapshots_camaras",
    save_file: bool = True,
    do_ocr: bool = True,
) -> dict:
    """
    Captura foto de la camara de cedula entrada peatonal.

    Args:
        output_dir: Directorio donde guardar la foto

    Returns:
        dict con estado de la captura {'success': bool, 'file': str, 'size': int}
    """
    ip = CAMERA_IP

    output_file = None
    if save_file:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"camara_cedula_entrada_peatonal_{timestamp}.jpg")

    try:
        capture_started = time.perf_counter()
        response = SESSION.get(
            SNAPSHOT_URL,
            auth=SNAPSHOT_AUTH,
            timeout=SNAPSHOT_TIMEOUT,
            stream=False,
        )
        capture_http_ms = int((time.perf_counter() - capture_started) * 1000)

        if response.status_code == 200 and len(response.content) > 1000:
            image_bytes_raw = response.content
            ocr_data = None
            ocr_error = None
            if do_ocr:
                try:
                    ocr_data = _extract_ocr_with_zone_fallback(image_bytes_raw)
                except Exception as exc:
                    ocr_error = str(exc)

            image_bytes = image_bytes_raw
            crop_boxes = None
            draw_route = None
            if isinstance(ocr_data, dict):
                draw_route = "found_in_zone_1" if ocr_data.get("cedula_source") == "crop_zone_1" else "not_found_in_zone_1"

            should_draw_boxes = draw_route in {"found_in_zone_1", "not_found_in_zone_1"}
            if DRAW_CROP_BOXES and should_draw_boxes:
                boxed_bytes, crop_boxes = _draw_crop_boxes(image_bytes, draw_route)
                if boxed_bytes:
                    image_bytes = boxed_bytes

            if output_file:
                with open(output_file, "wb") as f:
                    f.write(image_bytes)

            file_size = len(image_bytes)
            return {
                "success": True,
                "file": output_file,
                "size": file_size,
                "image_bytes": image_bytes,
                "crop_boxes": crop_boxes,
                "ocr_data": ocr_data,
                "ocr_error": ocr_error,
                "camera": "Camara Cedula Entrada Peatonal",
                "ip": ip,
                "timings": {
                    "capture_http_ms": capture_http_ms,
                    "capture_method": "http_snapshot_digest",
                },
            }

        return {
            "success": False,
            "file": None,
            "size": None,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": ip,
            "error": f"HTTP code: {response.status_code}",
            "timings": {
                "capture_http_ms": capture_http_ms,
                "capture_method": "http_snapshot_digest",
            },
        }
    except requests.ConnectTimeout:
        return {
            "success": False,
            "file": None,
            "size": None,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": ip,
            "error": "Connection timeout - Camera unreachable",
        }
    except requests.Timeout:
        return {
            "success": False,
            "file": None,
            "size": None,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": ip,
            "error": "Timeout",
        }
    except Exception as e:
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
        return {
            "success": False,
            "file": None,
            "size": None,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": ip,
            "error": str(e),
        }
