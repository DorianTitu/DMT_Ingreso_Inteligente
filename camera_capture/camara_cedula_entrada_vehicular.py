"""
Captura de camara cedula entrada vehicular (Camera250)
Protocolo: RTSP (ffmpeg)
"""

import os
import subprocess
import time
from datetime import datetime

from PIL import Image

from .runtime_helpers import format_ffmpeg_error, get_ffmpeg_path

MIN_VALID_IMAGE_BYTES = 9000
CAPTURE_TRANSPORT_ORDER = ('udp', 'tcp')
CAMERA_IP = '192.168.1.4'
CAMERA_USER = 'admin'
CAMERA_PASSWORD = 'DMT_1990'
CAMERA_CHANNEL = 1
CAMERA_SUBTYPE = 0
RTSP_PROBE_SIZE = '32768'
RTSP_ANALYZE_DURATION = '200000'


def _build_ffmpeg_cmd(rtsp_url: str, output_file: str, transport: str) -> list[str]:
	return [
		get_ffmpeg_path(),
		'-nostdin',
		'-hide_banner',
		'-loglevel', 'error',
		'-probesize', RTSP_PROBE_SIZE,
		'-analyzeduration', RTSP_ANALYZE_DURATION,
		'-rtsp_transport', transport,
		'-i', rtsp_url,
		'-map', '0:v:0',
		'-vf', 'scale=trunc(iw*sar):ih,setsar=1',
		'-vframes', '1',
		'-q:v', '3',
		'-y',
		output_file,
	]


def _is_valid_capture_file(file_path: str, min_bytes: int = MIN_VALID_IMAGE_BYTES) -> tuple[bool, str | None]:
	if not os.path.exists(file_path):
		return False, 'archivo no generado'

	size_bytes = os.path.getsize(file_path)
	if size_bytes < min_bytes:
		return False, f'captura invalida (size={size_bytes} bytes, min={min_bytes})'

	try:
		with Image.open(file_path) as img:
			img.verify()
	except Exception as exc:
		return False, f'captura invalida (jpg corrupto: {exc})'

	return True, None


def capture_camera250(output_dir: str = 'snapshots_camaras') -> dict:
	"""Captura foto de la camara de cedula vehicular y retorna solo captura."""
	ip = CAMERA_IP
	user = CAMERA_USER
	password = CAMERA_PASSWORD
	rtsp_url = (
		f'rtsp://{user}:{password}@{ip}:554/'
		f'cam/realmonitor?channel={CAMERA_CHANNEL}&subtype={CAMERA_SUBTYPE}'
	)

	os.makedirs(output_dir, exist_ok=True)
	timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
	output_file = os.path.join(output_dir, f'camara_cedula_entrada_vehicular_{timestamp}.jpg')

	try:
		errors = []

		for transport in CAPTURE_TRANSPORT_ORDER:
			capture_started = time.perf_counter()
			cmd = _build_ffmpeg_cmd(rtsp_url, output_file, transport)
			result = subprocess.run(cmd, capture_output=True, timeout=10)

			if result.returncode == 0 and os.path.exists(output_file):
				is_valid_capture, invalid_reason = _is_valid_capture_file(output_file)
			else:
				is_valid_capture, invalid_reason = False, None

			if is_valid_capture:
				file_size = os.path.getsize(output_file)
				capture_ms = int((time.perf_counter() - capture_started) * 1000)
				return {
					'success': True,
					'file': output_file,
					'size': file_size,
					'camera': 'Camera250 (Cedula)',
					'ip': ip,
					'timings': {
						'capture_ms': capture_ms,
						'capture_method': f'rtsp_{transport}',
					},
				}

			if os.path.exists(output_file):
				if invalid_reason:
					errors.append(f'{transport.upper()}: {invalid_reason}')
				else:
					size_bytes = os.path.getsize(output_file)
					errors.append(f'{transport.upper()}: captura invalida (size={size_bytes} bytes)')
			else:
				errors.append(f'{transport.upper()}: {format_ffmpeg_error(result.returncode, result.stderr)}')

			if os.path.exists(output_file):
				os.remove(output_file)

		return {
			'success': False,
			'file': None,
			'size': None,
			'camera': 'Camera250 (Cedula)',
			'ip': ip,
			'error': ' | '.join(errors),
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
			'error': 'Timeout',
		}
	except Exception as exc:
		if os.path.exists(output_file):
			os.remove(output_file)
		return {
			'success': False,
			'file': None,
			'size': None,
			'camera': 'Camera250 (Cedula)',
			'ip': ip,
			'error': str(exc),
		}

