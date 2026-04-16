#!/usr/bin/env python3
"""Captura un snapshot RTSP de la camara de ingreso peatonal."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

try:
    from .runtime_helpers import format_ffmpeg_error, get_ffmpeg_path
except ImportError:  # Soporta ejecucion directa del script
    from runtime_helpers import format_ffmpeg_error, get_ffmpeg_path

# ========== CONFIGURACION ==========
DVR_IP = "192.168.1.148"
DVR_USUARIO = "admin"
DVR_CONTRASENA = "DMT_1990"
DVR_PUERTO_RTSP = 554
CANAL = 2  # Canal 2 = Usuario vehicular
CAPTURE_TIMEOUT_SECONDS = 20

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("SNAPSHOT_OUTPUT_DIR", BASE_DIR / "snapshots_camaras"))

LOGGER = logging.getLogger("camera_capture.cedula_entrada_peatonal")


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


def _capture_snapshot(output_dir: Path) -> tuple[Path, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"camara_cedula_entrada_peatonal_{timestamp}.jpg"
    rtsp_url = build_rtsp_url()

    cmd = [
        get_ffmpeg_path(),
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-vframes",
        "1",
        "-q:v",
        "5",
        "-y",
        str(output_file),
    ]

    LOGGER.info("Iniciando captura RTSP")
    capture_started = time.perf_counter()
    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=CAPTURE_TIMEOUT_SECONDS,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(format_ffmpeg_error(result.returncode, result.stderr))

    if not output_file.exists():
        raise RuntimeError("ffmpeg termino sin generar el archivo de salida")

    capture_ms = int((time.perf_counter() - capture_started) * 1000)
    return output_file, capture_ms


def capture_cedula_entrada_peatonal(
    output_dir: str = "snapshots_camaras",
    save_file: bool = True,
) -> dict:
    """Captura imagen de cédula entrada peatonal y retorna metadata estandar."""
    output_path = Path(output_dir)

    try:
        output_file, capture_ms = _capture_snapshot(output_path)
        image_bytes = output_file.read_bytes()

        if not save_file:
            try:
                output_file.unlink(missing_ok=True)
            except OSError:
                pass

        return {
            "success": True,
            "file": str(output_file) if save_file else None,
            "size": len(image_bytes),
            "image_bytes": image_bytes,
            "camera": "Camara Cedula Entrada Peatonal",
            "ip": DVR_IP,
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
        output_file, capture_ms = _capture_snapshot(OUTPUT_DIR)
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