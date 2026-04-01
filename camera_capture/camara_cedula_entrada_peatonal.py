"""
Captura de camara de cedula entrada peatonal (192.168.1.3)
Protocolo: HTTP con autenticacion Digest
"""

import os
from io import BytesIO
from datetime import datetime
import time
import re

import requests
from PIL import Image, ImageDraw
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

# Zonas editables en porcentaje (x1, y1, x2, y2) para ajustar recortes visualmente.
CROP_ZONE_1_PCT = (0.37, 0.15, 0.98, 0.50)
CROP_ZONE_2_PCT = (0.12, 0.80, 0.40, 0.98)
DRAW_CROP_BOXES = True
BOX_WIDTH = 5


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

            draw = ImageDraw.Draw(img)
            color_1 = (0, 200, 0) if cedula_source == "crop_zone_1" else (255, 0, 0)
            color_2 = (0, 200, 0) if cedula_source == "crop_zone_2" else (255, 0, 0)
            draw.rectangle(zone_1_px, outline=color_1, width=BOX_WIDTH)
            draw.rectangle(zone_2_px, outline=color_2, width=BOX_WIDTH)

            output = BytesIO()
            img.save(output, format="JPEG", quality=95)
            return output.getvalue(), {
                "crop_zone_1_pct": CROP_ZONE_1_PCT,
                "crop_zone_2_pct": CROP_ZONE_2_PCT,
                "crop_zone_1_px": zone_1_px,
                "crop_zone_2_px": zone_2_px,
                "cedula_source": cedula_source,
            }
    except Exception:
        return None, None


def _extract_ocr_with_zone_fallback(image_bytes: bytes) -> dict:
    started = time.perf_counter()
    with Image.open(BytesIO(image_bytes)) as img:
        zone_1_px = _rect_pct_to_pixels(img.size, CROP_ZONE_1_PCT)
        zone_2_px = _rect_pct_to_pixels(img.size, CROP_ZONE_2_PCT)

        crop_started = time.perf_counter()
        zone_1_img = img.crop(zone_1_px)
        zone_2_img = img.crop(zone_2_px)
        crop_ms = int((time.perf_counter() - crop_started) * 1000)

    reader = _get_ocr_reader()
    ocr_started = time.perf_counter()

    # OCR de zona 1 para nombres/apellidos y primer intento de cedula.
    zone_1_lines = _ocr_lines(reader, _preprocess_image_for_ocr(zone_1_img))

    def _clean_words(line: str) -> str:
        cleaned = re.sub(r"[^A-Za-zA-Z\s]", " ", line)
        return " ".join(cleaned.split()).upper()

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

    def _extract_combined_names(lines: list[str]) -> tuple[str | None, str | None]:
        header_idx = -1
        for idx, line in enumerate(lines):
            key = line.upper()
            if ("APELLIDOS" in key or "PELLIDOS" in key) and ("NOMBRE" in key or "NOMBRES" in key):
                header_idx = idx
                break

        values = []
        if header_idx >= 0:
            search_lines = lines[header_idx + 1:]
        else:
            search_lines = lines

        for line in search_lines:
            key = line.upper()
            if "LUGAR" in key or "NACIMIENTO" in key or "NACIONALIDAD" in key or "SEXO" in key:
                break
            if "CEDULA" in key or "CIUDADAN" in key or "REGISTRO" in key:
                continue
            if re.search(r"\d", key):
                continue
            cleaned = _clean_words(line)
            if not cleaned:
                continue
            if len(cleaned.split()) < 2:
                continue
            values.append(cleaned)
            if len(values) >= 2:
                break

        if not values:
            return _extract_name_parts(lines)

        if len(values) == 1:
            tokens = values[0].split()
            if len(tokens) >= 3:
                apellidos_val = " ".join(tokens[:2])
                nombres_val = " ".join(tokens[2:4])
                return apellidos_val, nombres_val
            return values[0], None

        apellidos_tokens = values[0].split()
        nombres_tokens = values[1].split()
        apellidos_val = " ".join(apellidos_tokens[:2]) if apellidos_tokens else None
        nombres_val = " ".join(nombres_tokens[:2]) if nombres_tokens else None
        return apellidos_val, nombres_val

    cedula = _extract_cedula_zone_1(zone_1_lines)
    cedula_source = "crop_zone_1"
    fallback_used = False

    if not cedula:
        # Solo si zona 1 no detecta cedula, se ejecuta zona 2 para cédula.
        zone_2_lines = _ocr_lines(
            reader,
            _preprocess_image_for_ocr(zone_2_img),
            allowlist='0123456789NUI.NO'
        )
        cedula = _extract_cedula_zone_1(zone_2_lines)
        if cedula:
            cedula_source = "crop_zone_2"
            fallback_used = True

    # Regla de formato:
    # - Si cedula viene de zona 1: nombres y apellidos en campo combinado.
    # - Si cedula viene de zona 2: nombres/apellidos en campos separados.
    if cedula_source == "crop_zone_1":
        apellidos, nombres = _extract_combined_names(zone_1_lines)
    else:
        apellidos, nombres = _extract_name_parts(zone_1_lines)

    apellidos = _sanitize_apellidos(apellidos)
    nombres = _sanitize_nombres(nombres)

    ocr_ms = int((time.perf_counter() - ocr_started) * 1000)
    total_ms = int((time.perf_counter() - started) * 1000)

    return {
        "cedula": cedula,
        "nombres": nombres,
        "apellidos": apellidos,
        "cedula_source": cedula_source,
        "tiempos_ms": {
            "crop_ms": crop_ms,
            "crop_ok": True,
            "ocr_ms": ocr_ms,
            "parse_ms": 0,
            "total_ms": total_ms,
            "cedula_fallback_used": fallback_used,
        },
    }


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
    ip = "192.168.1.3"
    user = "admin"
    password = "DMT_1990"
    url = f"http://{ip}/cgi-bin/snapshot.cgi"

    output_file = None
    if save_file:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"camara_cedula_entrada_peatonal_{timestamp}.jpg")

    try:
        response = SESSION.get(
            url,
            auth=HTTPDigestAuth(user, password),
            timeout=(2, 6),
            stream=False,
        )

        if response.status_code == 200 and len(response.content) > 1000:
            image_bytes_raw = response.content
            ocr_data = None
            ocr_error = None
            cedula_source = None
            if do_ocr:
                try:
                    ocr_data = _extract_ocr_with_zone_fallback(image_bytes_raw)
                    if isinstance(ocr_data, dict):
                        cedula_source = ocr_data.get("cedula_source")
                except Exception as exc:
                    ocr_error = str(exc)

            image_bytes = image_bytes_raw
            crop_boxes = None
            if DRAW_CROP_BOXES:
                boxed_bytes, crop_boxes = _draw_crop_boxes(image_bytes, cedula_source)
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
            }

        return {
            "success": False,
            "file": None,
            "size": None,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": ip,
            "error": f"HTTP code: {response.status_code}",
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
