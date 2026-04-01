"""
Captura de camara de cedula entrada peatonal (192.168.1.3)
Protocolo: HTTP con autenticacion Digest
"""

import os
from io import BytesIO
from datetime import datetime

import requests
from PIL import Image, ImageDraw
from requests.auth import HTTPDigestAuth

SESSION = requests.Session()
SESSION.headers.update({"Connection": "keep-alive"})

# Zonas editables en porcentaje (x1, y1, x2, y2) para ajustar recortes visualmente.
CROP_ZONE_1_PCT = (0.40, 0.15, 0.98, 0.50)
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


def _draw_crop_boxes(image_bytes: bytes) -> tuple[bytes, dict] | tuple[None, None]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            zone_1_px = _rect_pct_to_pixels(img.size, CROP_ZONE_1_PCT)
            zone_2_px = _rect_pct_to_pixels(img.size, CROP_ZONE_2_PCT)

            draw = ImageDraw.Draw(img)
            draw.rectangle(zone_1_px, outline=(255, 0, 0), width=BOX_WIDTH)
            draw.rectangle(zone_2_px, outline=(0, 200, 0), width=BOX_WIDTH)

            output = BytesIO()
            img.save(output, format="JPEG", quality=95)
            return output.getvalue(), {
                "crop_zone_1_pct": CROP_ZONE_1_PCT,
                "crop_zone_2_pct": CROP_ZONE_2_PCT,
                "crop_zone_1_px": zone_1_px,
                "crop_zone_2_px": zone_2_px,
            }
    except Exception:
        return None, None


def capture_cedula_entrada_peatonal(output_dir: str = "snapshots_camaras", save_file: bool = True) -> dict:
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
            image_bytes = response.content
            crop_boxes = None
            if DRAW_CROP_BOXES:
                boxed_bytes, crop_boxes = _draw_crop_boxes(image_bytes)
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
