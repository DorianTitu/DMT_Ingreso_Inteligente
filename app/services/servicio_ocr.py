"""
Servicio de OCR
Extrae datos de cédulas usando EasyOCR
"""

import base64
import binascii
import re
import time
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.services.ocr_cedula_entrada_vehicular import (
    warmup_cedula_ocr_reader,
    extract_cedula_data_from_bytes,
)
from app.services.ocr_cedula_entrada_peatonal import (
    extract_cedula_data_from_bytes as extract_cedula_data_from_bytes_peatonal,
)


class ServicioOCR:
    """Servicio de prec I aeso OCR de cédulas"""

    @staticmethod
    def _decode_base64_image(base64_data: str) -> bytes:
        """Decodifica base64 tolerando data URL, espacios por '+' y padding faltante."""
        if not isinstance(base64_data, str) or not base64_data.strip():
            raise HTTPException(status_code=400, detail="La imagen base64 esta vacia")

        clean_data = base64_data.strip()
        if ',' in clean_data:
            clean_data = clean_data.split(',', 1)[1]

        # Algunos clientes envian base64 por query y '+' llega como espacio.
        clean_data = clean_data.replace(' ', '+')
        clean_data = re.sub(r'\s+', '', clean_data)

        # Rellena padding cuando el largo no es multiplo de 4.
        missing_padding = len(clean_data) % 4
        if missing_padding:
            clean_data += '=' * (4 - missing_padding)

        try:
            image_bytes = base64.b64decode(clean_data, validate=True)
        except (binascii.Error, ValueError):
            try:
                image_bytes = base64.urlsafe_b64decode(clean_data)
            except (binascii.Error, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"Base64 invalido: {exc}")

        if not image_bytes:
            raise HTTPException(status_code=400, detail="La imagen base64 esta vacia")

        return image_bytes
    
    @staticmethod
    def warmup_ocr():
        """Precarga el modelo OCR para mejor rendimiento"""
        try:
            warmup_cedula_ocr_reader()
            print("[OCR] EasyOCR precargado correctamente")
            return True
        except Exception as exc:
            print(f"[OCR] No se pudo precargar EasyOCR: {exc}")
            return False
    
    @staticmethod
    def extract_cedula_from_base64(base64_data: str) -> JSONResponse:
        """Procesa OCR desde base64 y retorna resultado uniforme"""
        started = time.perf_counter()

        image_bytes = ServicioOCR._decode_base64_image(base64_data)

        ocr_data = extract_cedula_data_from_bytes(image_bytes)
        total_ms = int((time.perf_counter() - started) * 1000)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "ocr_data": ocr_data,
                "timings": {
                    "endpoint_total_ms": total_ms
                },
                "message": "Extraccion OCR vehicular exitosa"
            }
        )

    @staticmethod
    def extract_cedula_peatonal_from_base64(base64_data: str) -> JSONResponse:
        """Procesa OCR peatonal desde base64 y retorna resultado uniforme"""
        started = time.perf_counter()

        image_bytes = ServicioOCR._decode_base64_image(base64_data)

        ocr_data = extract_cedula_data_from_bytes_peatonal(image_bytes)
        total_ms = int((time.perf_counter() - started) * 1000)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "ocr_data": ocr_data,
                "timings": {
                    "endpoint_total_ms": total_ms
                },
                "message": "Extraccion OCR peatonal exitosa"
            }
        )
