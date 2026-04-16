#!/usr/bin/env python3
"""Captura un snapshot RTSP de la camara de ingreso peatonal."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from io import BytesIO
from datetime import datetime
from pathlib import Path
from PIL import Image

try:
    from .runtime_helpers import format_ffmpeg_error, get_ffmpeg_path
except ImportError:  # Soporta ejecucion directa del script
    from runtime_helpers import format_ffmpeg_error, get_ffmpeg_path

# ========== CONFIGURACION ==========
DVR_IP = "192.168.1.148"
DVR_USUARIO = "admin"
DVR_CONTRASENA = "DMT_1990"
DVR_PUERTO_RTSP = 554
CANAL = 4  # Canal 4 = Cedula entrada vehicular
CAPTURE_TIMEOUT_SECONDS = 20


VEHICULAR_CROP_ZONE_2_PCT = (0.30, 0.25, 0.65, 0.55)
VEHICULAR_CROP_ZONE_3_PCT = (0.65, 0.20, 0.98, 0.40)


VEHICULAR_CROP_ZONES_PCT: list[tuple[float, float, float, float]] = [
    VEHICULAR_CROP_ZONE_2_PCT,
    VEHICULAR_CROP_ZONE_3_PCT,
]

# Unico recorte rectangular por 2 vertices (x, y):
# [esquina_superior_izquierda, esquina_inferior_derecha]
SINGLE_CROP_VERTICES: list[tuple[float, float]] = [
    (0.10, 0.09),
    (0.86, 0.88),
    #(0.33, 0.20),
    #(0.60, 0.45),
]

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("SNAPSHOT_OUTPUT_DIR", BASE_DIR / "snapshots_camaras"))

LOGGER = logging.getLogger("camera_capture.cedula_entrada_vehicular")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def build_rtsp_url() -> str:
    return (
        f"rtsp://{DVR_USUARIO}:{DVR_CONTRASENA}@{DVR_IP}:{DVR_PUERTO_RTSP}"
        f"/cam/realmonitor?channel={CANAL}&subtype=0"
    )


def _capture_snapshot_bytes() -> tuple[bytes, int]:
    rtsp_url = build_rtsp_url()

    cmd = [
        get_ffmpeg_path(),
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-frames:v",
        "1",
        "-q:v",
        "5",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]

    LOGGER.info("Iniciando captura RTSP")
    capture_started = time.perf_counter()
    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=CAPTURE_TIMEOUT_SECONDS,
        check=False,
    )

    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        raise RuntimeError(format_ffmpeg_error(result.returncode, stderr_text))

    if not result.stdout:
        raise RuntimeError("ffmpeg termino sin generar datos de imagen")

    capture_ms = int((time.perf_counter() - capture_started) * 1000)
    return result.stdout, capture_ms


def _apply_single_crop_by_vertices(
    image_bytes: bytes,
    vertices: list[tuple[float, float]],
) -> tuple[bytes, tuple[int, int, int, int]]:
    if len(vertices) != 2:
        raise ValueError("Debes indicar exactamente 2 vertices para el recorte")

    image = Image.open(BytesIO(image_bytes)).convert("RGB")

    width, height = image.size
    (x1, y1), (x2, y2) = vertices

    def _to_pixel(value: float, max_size: int) -> int:
        # Si viene normalizado (0..1), se escala al tamano real de la imagen.
        if 0.0 <= value <= 1.0:
            return int(round(value * (max_size - 1)))
        return int(value)

    left, right = sorted((_to_pixel(float(x1), width), _to_pixel(float(x2), width)))
    top, bottom = sorted((_to_pixel(float(y1), height), _to_pixel(float(y2), height)))

    left = max(0, min(left, width - 1))
    right = max(1, min(right, width))
    top = max(0, min(top, height - 1))
    bottom = max(1, min(bottom, height))

    if right <= left or bottom <= top:
        raise ValueError("Los 2 vertices no definen un recorte valido")

    bbox = (left, top, right, bottom)
    cropped = image.crop(bbox)

    output = BytesIO()
    cropped.save(output, format="JPEG", quality=95)
    return output.getvalue(), bbox


def _draw_vehicular_zones(
    image_bytes: bytes,
) -> tuple[bytes, list[dict[str, int]]]:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = image.size

    boxes: list[dict[str, int]] = []
    for index, (x_min, y_min, x_max, y_max) in enumerate(VEHICULAR_CROP_ZONES_PCT, start=1):
        left = int(round(x_min * (width - 1)))
        top = int(round(y_min * (height - 1)))
        right = int(round(x_max * (width - 1)))
        bottom = int(round(y_max * (height - 1)))

        left, right = sorted((left, right))
        top, bottom = sorted((top, bottom))

        left = max(0, min(left, width - 1))
        right = max(1, min(right, width - 1))
        top = max(0, min(top, height - 1))
        bottom = max(1, min(bottom, height - 1))

        # draw.rectangle((left, top, right, bottom), outline=(0, 255, 0), width=3)
        # draw.text((left + 4, max(0, top - 18)), f"Z{index}", fill=(0, 255, 0))

        boxes.append(
            {
                "zone": index,
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
            }
        )

    output = BytesIO()
    # Se conserva la imagen original recortada sin pintar las zonas.
    image.save(output, format="JPEG", quality=95)
    return output.getvalue(), boxes


def capture_cedula_entrada_peatonal(
    output_dir: str = "snapshots_camaras",
    save_file: bool = True,
) -> dict:
    """Captura imagen de cédula entrada peatonal y retorna metadata estandar."""
    output_path = Path(output_dir)

    try:
        image_bytes, capture_ms = _capture_snapshot_bytes()
        # Primero se aplica el recorte general y luego solo se calculan las zonas.
        image_bytes, crop_bbox = _apply_single_crop_by_vertices(
            image_bytes,
            SINGLE_CROP_VERTICES,
        )
        image_bytes, zone_boxes = _draw_vehicular_zones(image_bytes)

        output_file = None
        if save_file:
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_path / f"camara_cedula_entrada_peatonal_{timestamp}.jpg"
            output_file.write_bytes(image_bytes)

        return {
            "success": True,
            "file": str(output_file) if output_file else None,
            "size": len(image_bytes),
            "image_bytes": image_bytes,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": DVR_IP,
            "zone_boxes": zone_boxes,
            "crop_vertices": SINGLE_CROP_VERTICES,
            "crop_bbox": {
                "left": crop_bbox[0],
                "top": crop_bbox[1],
                "right": crop_bbox[2],
                "bottom": crop_bbox[3],
            },
            "timings": {
                "capture_ms": capture_ms,
                "capture_method": "rtsp_tcp",
            },
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "file": None,
            "size": None,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": DVR_IP,
            "error": "Timeout",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "file": None,
            "size": None,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": DVR_IP,
            "error": "ffmpeg no encontrado en PATH",
        }
    except Exception as exc:
        return {
            "success": False,
            "file": None,
            "size": None,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": DVR_IP,
            "error": str(exc),
        }


def capture_camera3(output_dir: str = "snapshots_camaras", save_file: bool = True) -> dict:
    """Compatibilidad con el contrato usado por servicios/rutas para usuario vehicular."""
    result = capture_cedula_entrada_peatonal(output_dir=output_dir, save_file=save_file)
    if isinstance(result, dict):
        result["camera"] = "Camera3 (Usuario)"
    return result


def capture_camera250(output_dir: str = "snapshots_camaras", save_file: bool = True) -> dict:
    """Alias de compatibilidad para captura de cédula vehicular."""
    result = capture_cedula_entrada_peatonal(output_dir=output_dir, save_file=save_file)
    if isinstance(result, dict):
        result["camera"] = "Camera250 (Cedula Vehicular)"
    return result


def main() -> int:
    configure_logging()

    LOGGER.info("Configuracion de captura cargada")
    LOGGER.info(
        "DVR=%s:%s canal=%s usuario=%s output_dir=%s",
        DVR_IP,
        DVR_PUERTO_RTSP,
        CANAL,
        DVR_USUARIO,
        OUTPUT_DIR,
    )

    try:
        image_bytes, capture_ms = _capture_snapshot_bytes()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"camara_cedula_entrada_peatonal_{timestamp}.jpg"
        output_file.write_bytes(image_bytes)
        size = output_file.stat().st_size
        LOGGER.info("Captura completada correctamente")
        LOGGER.info("Archivo generado: %s", output_file)
        LOGGER.info("Tamano: %s bytes (%.1f KB)", size, size / 1024)
        LOGGER.info("Tiempo de captura: %s ms", capture_ms)
        return 0
    except subprocess.TimeoutExpired:
        LOGGER.exception(
            "Timeout de captura: ffmpeg supero %s segundos",
            CAPTURE_TIMEOUT_SECONDS,
        )
        return 1
    except FileNotFoundError:
        LOGGER.exception("No se encontro ffmpeg en el PATH")
        return 1
    except Exception:
        LOGGER.exception("Fallo inesperado durante la captura")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())