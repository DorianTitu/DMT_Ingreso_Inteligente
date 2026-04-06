"""
Servicio de OCR
Extrae datos de cédulas usando EasyOCR
"""

import base64
import binascii
import time
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from camera_capture.camara_cedula_entrada_vehicular import (
    warmup_cedula_ocr_reader,
    extract_cedula_data_from_bytes,
)


class ServicioOCR:
    """Servicio de prec I aeso OCR de cédulas"""
    
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
        
        # Limpiar base64 si tiene prefijo
        clean_data = base64_data.split(',', 1)[1] if ',' in base64_data else base64_data
        
        try:
            image_bytes = base64.b64decode(clean_data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Base64 invalido: {exc}")

        if not image_bytes:
            raise HTTPException(status_code=400, detail="La imagen base64 esta vacia")

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
                "message": "Extraccion OCR exitosa"
            }
        )
