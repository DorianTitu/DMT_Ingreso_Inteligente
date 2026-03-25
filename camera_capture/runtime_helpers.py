"""
Helpers compartidos para ejecución de capturas.
"""

import shutil


def get_ffmpeg_path() -> str:
    """
    Obtiene la ruta del ejecutable ffmpeg.
    Intenta usar imageio-ffmpeg primero, luego busca en PATH.
    """
    try:
        import imageio_ffmpeg

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_path:
            return ffmpeg_path
    except Exception:
        pass

    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        return ffmpeg

    return 'ffmpeg'


def format_ffmpeg_error(returncode: int, stderr: bytes | str) -> str:
    """Genera un error legible para depurar fallos de ffmpeg en Windows."""
    if isinstance(stderr, bytes):
        stderr_text = stderr.decode(errors='ignore')
    else:
        stderr_text = stderr or ""

    signed_code = returncode - (1 << 32) if returncode > 0x7FFFFFFF else returncode
    stderr_tail = stderr_text.strip().splitlines()[-1] if stderr_text.strip() else "sin detalle en stderr"
    return f"Exit code: {returncode} (signed: {signed_code}) - {stderr_tail}"
