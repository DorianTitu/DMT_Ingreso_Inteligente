"""
Prueba de conexion y captura para nuevas camaras IP.

- IPs: 172.168.1.3 y 172.168.1.224
- Usuario: admin
- Claves a probar: dmt_2390 y DMT_1990

El script intenta capturar por HTTP snapshot (Digest y Basic) y por RTSP (UDP/TCP).
Guarda las imagenes en snapshots_prueba_nuevas/ dentro del proyecto.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

try:
    from camera_capture.runtime_helpers import get_ffmpeg_path, format_ffmpeg_error
except Exception:
    # Fallback para ejecucion desde otros contextos.
    def get_ffmpeg_path() -> str:
        return "ffmpeg"

    def format_ffmpeg_error(returncode: int, stderr: bytes | str) -> str:
        if isinstance(stderr, bytes):
            stderr_text = stderr.decode(errors="ignore")
        else:
            stderr_text = stderr or ""
        tail = stderr_text.strip().splitlines()[-1] if stderr_text.strip() else "sin detalle"
        return f"Exit code: {returncode} - {tail}"


CAMERA_IPS = ["192.168.1.3", "192.168.1.224"]
USERNAME = "admin"
PASSWORDS = ["dmt_2390", "DMT_1990"]
OUTPUT_DIR = Path("snapshots_prueba_nuevas")
HTTP_TIMEOUT = 4
RTSP_TIMEOUT = 6
CAPTURE_TRANSPORT_ORDER = ("udp", "tcp")
CAMERA_CHANNEL = 1
CAMERA_SUBTYPE = 0


@dataclass
class CaptureResult:
    success: bool
    ip: str
    password: str
    method: str
    file: str | None
    detail: str
    size: int | None = None


def _build_http_output(ip: str, password: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ip = ip.replace(".", "_")
    safe_pwd = "pwd1" if password == PASSWORDS[0] else "pwd2"
    return OUTPUT_DIR / f"cam_{safe_ip}_http_{safe_pwd}_{ts}.jpg"


def _build_rtsp_output(ip: str, password: str, transport: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ip = ip.replace(".", "_")
    safe_pwd = "pwd1" if password == PASSWORDS[0] else "pwd2"
    return OUTPUT_DIR / f"cam_{safe_ip}_rtsp_{transport}_{safe_pwd}_{ts}.jpg"


def _try_http_snapshot(ip: str, password: str) -> CaptureResult:
    url = f"http://{ip}/cgi-bin/snapshot.cgi"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = _build_http_output(ip, password)

    auth_attempts = [
        ("digest", HTTPDigestAuth(USERNAME, password)),
        ("basic", HTTPBasicAuth(USERNAME, password)),
    ]
    last_error = "sin respuesta"

    for auth_name, auth in auth_attempts:
        try:
            response = requests.get(url, auth=auth, timeout=HTTP_TIMEOUT, stream=True)
            if response.status_code == 200 and len(response.content) > 1000:
                with open(output_file, "wb") as f:
                    f.write(response.content)
                size = output_file.stat().st_size
                return CaptureResult(
                    success=True,
                    ip=ip,
                    password=password,
                    method=f"http-{auth_name}",
                    file=str(output_file),
                    detail=f"HTTP {auth_name} OK",
                    size=size,
                )
        except requests.RequestException as exc:
            last_error = str(exc)
        else:
            last_error = f"HTTP {auth_name} status={response.status_code}, bytes={len(response.content)}"

    if output_file.exists() and output_file.stat().st_size == 0:
        output_file.unlink(missing_ok=True)

    return CaptureResult(
        success=False,
        ip=ip,
        password=password,
        method="http",
        file=None,
        detail=last_error,
    )


def _build_ffmpeg_cmd(rtsp_url: str, output_file: Path, transport: str) -> list[str]:
    return [
        get_ffmpeg_path(),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-probesize",
        "32768",
        "-analyzeduration",
        "200000",
        "-rtsp_transport",
        transport,
        "-i",
        rtsp_url,
        "-map",
        "0:v:0",
        "-vf",
        "scale=trunc(iw*sar):ih,setsar=1",
        "-vframes",
        "1",
        "-q:v",
        "3",
        "-y",
        str(output_file),
    ]


def _try_rtsp_snapshot(ip: str, password: str) -> CaptureResult:
    rtsp_url = (
        f"rtsp://{USERNAME}:{password}@{ip}:554/"
        f"cam/realmonitor?channel={CAMERA_CHANNEL}&subtype={CAMERA_SUBTYPE}"
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    for transport in CAPTURE_TRANSPORT_ORDER:
        output_file = _build_rtsp_output(ip, password, transport)
        cmd = _build_ffmpeg_cmd(rtsp_url, output_file, transport)

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=RTSP_TIMEOUT)
        except subprocess.TimeoutExpired:
            output_file.unlink(missing_ok=True)
            errors.append(f"{transport.upper()}: timeout")
            continue

        if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 1000:
            size = output_file.stat().st_size
            return CaptureResult(
                success=True,
                ip=ip,
                password=password,
                method=f"rtsp-{transport}",
                file=str(output_file),
                detail="RTSP OK",
                size=size,
            )

        if output_file.exists():
            output_file.unlink(missing_ok=True)

        errors.append(f"{transport.upper()}: {format_ffmpeg_error(result.returncode, result.stderr)}")

    return CaptureResult(
        success=False,
        ip=ip,
        password=password,
        method="rtsp",
        file=None,
        detail=" | ".join(errors),
    )


def probe_camera(ip: str) -> dict[str, Any]:
    attempts: list[CaptureResult] = []

    for password in PASSWORDS:
        http_res = _try_http_snapshot(ip, password)
        attempts.append(http_res)
        if http_res.success:
            return {
                "ip": ip,
                "success": True,
                "credential": {"user": USERNAME, "password": password},
                "capture": http_res.__dict__,
                "attempts": [a.__dict__ for a in attempts],
            }

        rtsp_res = _try_rtsp_snapshot(ip, password)
        attempts.append(rtsp_res)
        if rtsp_res.success:
            return {
                "ip": ip,
                "success": True,
                "credential": {"user": USERNAME, "password": password},
                "capture": rtsp_res.__dict__,
                "attempts": [a.__dict__ for a in attempts],
            }

    return {
        "ip": ip,
        "success": False,
        "credential": None,
        "capture": None,
        "attempts": [a.__dict__ for a in attempts],
    }


def main() -> None:
    print("== PRUEBA NUEVAS CAMARAS ==")
    print(f"Output: {OUTPUT_DIR.resolve()}")

    results = [probe_camera(ip) for ip in CAMERA_IPS]

    print("\n== RESUMEN ==")
    for res in results:
        ip = res["ip"]
        if res["success"]:
            capture = res["capture"]
            cred = res["credential"]
            print(
                f"[OK] {ip} -> password='{cred['password']}' via {capture['method']} | "
                f"file={capture['file']} | size={capture['size']} bytes"
            )
        else:
            print(f"[FAIL] {ip} -> no se logro captura con ninguna clave/metodo")
            for attempt in res["attempts"]:
                print(
                    f"  - {attempt['method']} ({attempt['password']}): "
                    f"{attempt['detail']}"
                )


if __name__ == "__main__":
    main()
