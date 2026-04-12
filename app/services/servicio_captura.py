"""
Servicio de captura de cámaras
Orquesta las capturas ONVIF-Dahua
"""

import os
import base64
import time
from typing import Optional
from fastapi import HTTPException
from fastapi.responses import Response, JSONResponse

from camera_capture import (
    capture_camera1,
    capture_camera250,
    capture_cedula_entrada_peatonal,
)
from camera_capture.camara_usuario_entrada_vehicular import capture_camera3 as capture_usuario_entrada_vehicular
from camera_capture.camara_usuario_entrada_peatonal import capture_camera3 as capture_usuario_entrada_peatonal
from app.services.ocr_cedula_entrada_vehicular import (
    extract_cedula_data_from_bytes,
)
from app.services.ocr_cedula_entrada_peatonal import (
    extract_cedula_data_from_bytes as extract_cedula_data_from_bytes_peatonal,
)


class ServicioCaptura:
    """Servicio encargado de capturar imágenes de cámaras"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    @staticmethod
    def _extract_image_bytes(result: dict) -> bytes:
        """Obtiene bytes de imagen desde memoria o desde archivo temporal"""
        image_bytes = result.get('image_bytes')
        if isinstance(image_bytes, (bytes, bytearray)) and len(image_bytes) > 0:
            return bytes(image_bytes)

        captured_file = result.get('file')
        if not captured_file or not os.path.exists(captured_file):
            raise HTTPException(status_code=500, detail="No se encontro la imagen capturada")

        with open(captured_file, 'rb') as image_file:
            return image_file.read()
    
    @staticmethod
    def _cleanup_temp_capture_file(captured_file: Optional[str]) -> bool:
        """Limpia archivo temporal de captura"""
        if captured_file and os.path.exists(captured_file):
            try:
                os.remove(captured_file)
                return True
            except OSError:
                return False
        return False
    
    def build_capture_response(
        self,
        result: dict,
        error_prefix: str,
        include_data_url: bool = False,
        include_image: bool = True,
    ) -> JSONResponse:
        """Construye respuesta uniforme para capturas"""
        if not result.get('success'):
            raise HTTPException(
                status_code=500,
                detail=f"{error_prefix}: {result.get('error', 'Desconocido')}"
            )

        started = time.perf_counter()
        captured_file = result['file']
        image_base64 = None
        image_data_url = None
        encode_ms = 0
        
        if include_image:
            image_bytes = self._extract_image_bytes(result)
            encode_start = time.perf_counter()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            encode_ms = int((time.perf_counter() - encode_start) * 1000)
            image_data_url = f"data:image/jpeg;base64,{image_base64}" if include_data_url else None

        temp_file_removed = self._cleanup_temp_capture_file(captured_file)
        total_ms = int((time.perf_counter() - started) * 1000)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "camera": result['camera'],
                "ip": result['ip'],
                "file": captured_file,
                "temp_file_removed": temp_file_removed,
                "size_bytes": result['size'],
                "image_base64": image_base64,
                "image_data_url": image_data_url,
                "crop_boxes": result.get('crop_boxes'),
                "capture_crop_box_px": result.get('capture_crop_box_px'),
                "capture_original_size_px": result.get('capture_original_size_px'),
                "capture_cropped_size_px": result.get('capture_cropped_size_px'),
                "capture_crop_box_pct": result.get('capture_crop_box_pct'),
                "ocr_data": result.get('ocr_data'),
                "ocr_detected": result.get('ocr_detected'),
                "ocr_crops": result.get('ocr_crops'),
                "ocr_error": result.get('ocr_error'),
                "timings": {
                    **(result.get('timings') or {}),
                    "api_base64_encode_ms": encode_ms,
                    "api_response_total_ms": total_ms,
                },
                "message": "Captura exitosa"
            }
        )
    
    def build_capture_jpeg_response(self, result: dict, error_prefix: str) -> Response:
        """Retorna imagen JPEG binario para minimizar latencia"""
        if not result.get('success'):
            raise HTTPException(
                status_code=500,
                detail=f"{error_prefix}: {result.get('error', 'Desconocido')}"
            )

        image_bytes = self._extract_image_bytes(result)
        captured_file = result.get('file')
        temp_file_removed = self._cleanup_temp_capture_file(captured_file)

        headers = {
            'X-Camera': str(result.get('camera', '')),
            'X-Camera-IP': str(result.get('ip', '')),
            'X-Temp-File-Removed': str(temp_file_removed).lower(),
        }

        timings = result.get('timings') or {}
        if 'capture_http_ms' in timings:
            headers['X-Capture-Http-Ms'] = str(timings.get('capture_http_ms'))
        if 'capture_method' in timings:
            headers['X-Capture-Method'] = str(timings.get('capture_method'))
        if 'rtsp_fallback_ms' in timings:
            headers['X-RTSP-Fallback-Ms'] = str(timings.get('rtsp_fallback_ms'))

        return Response(content=image_bytes, media_type='image/jpeg', headers=headers)
    
    # ============ CAPTURA VEHICULAR ============
    
    def capture_placa_entrada_vehicular(
        self,
        include_data_url: bool = False,
        include_image: bool = True,
        response_mode: str = "json"
    ):
        """Captura imagen de Camera1 (placa entrada vehicular)"""
        result = capture_camera1(self.output_dir)
        if response_mode.lower() == "jpeg":
            return self.build_capture_jpeg_response(
                result,
                f"Error al capturar imagen de {result.get('camera', 'Camera1 (Placa)')}"
            )
        return self.build_capture_response(
            result,
            f"Error al capturar imagen de {result.get('camera', 'Camera1 (Placa)')}",
            include_data_url,
            include_image
        )
    
    def capture_usuario_entrada_vehicular(
        self,
        include_data_url: bool = False,
        include_image: bool = True,
        response_mode: str = "json"
    ):
        """Captura imagen de usuario entrada vehicular (Camera3)"""
        save_file = response_mode.lower() != "jpeg"
        result = capture_usuario_entrada_vehicular(self.output_dir, save_file=save_file)
        if response_mode.lower() == "jpeg":
            return self.build_capture_jpeg_response(
                result,
                f"Error al capturar imagen de {result.get('camera', 'Camera3 (Usuario)')}"
            )
        return self.build_capture_response(
            result,
            f"Error al capturar imagen de {result.get('camera', 'Camera3 (Usuario)')}",
            include_data_url,
            include_image
        )
    
    def capture_cedula_entrada_vehicular(
        self,
        include_data_url: bool = False,
        include_image: bool = True,
        response_mode: str = "json",
        do_ocr: bool = False,
        draw_boxes: bool = False,
        include_ocr_crops: bool = False,
    ):
        """Captura imagen de cédula entrada vehicular (Camera250)"""
        # Igual que peatonal: prioriza bytes en memoria para minimizar I/O en disco.
        result = capture_camera250(self.output_dir, save_file=False)

        if result.get('success') and do_ocr:
            ocr_error = None
            try:
                image_bytes = self._extract_image_bytes(result)
                ocr_data = extract_cedula_data_from_bytes(image_bytes)
                result['ocr_data'] = {
                    'cedula': ocr_data.get('cedula') if isinstance(ocr_data, dict) else None,
                    'nombres': ocr_data.get('nombres') if isinstance(ocr_data, dict) else None,
                    'apellidos': ocr_data.get('apellidos') if isinstance(ocr_data, dict) else None,
                }
                result['ocr_detected'] = result['ocr_data']
                result['ocr_error'] = None
            except Exception as exc:
                ocr_error = str(exc)
            if ocr_error:
                result['ocr_error'] = ocr_error

        if response_mode.lower() == "jpeg":
            return self.build_capture_jpeg_response(result, "Error en captura")
        return self.build_capture_response(
            result,
            "Error en captura",
            include_data_url,
            include_image
        )
    
    # ============ CAPTURA PEATONAL ============
    
    def capture_cedula_entrada_peatonal(
        self,
        include_data_url: bool = False,
        include_image: bool = True,
        response_mode: str = "json",
        do_ocr: bool = False,
    ):
        """Captura imagen de cédula entrada peatonal (192.168.1.3)"""
        # Evita I/O a disco para respuestas JSON: ya tenemos bytes en memoria.
        save_file = False
        result = capture_cedula_entrada_peatonal(
            self.output_dir,
            save_file=save_file,
        )
        if result.get('success') and do_ocr:
            ocr_error = None
            try:
                image_bytes = self._extract_image_bytes(result)
                ocr_data = extract_cedula_data_from_bytes_peatonal(image_bytes)
                result['ocr_data'] = ocr_data
                result['ocr_error'] = None
            except Exception as exc:
                ocr_error = str(exc)
            if ocr_error:
                result['ocr_error'] = ocr_error

        if response_mode.lower() == "jpeg":
            return self.build_capture_jpeg_response(
                result,
                "Error al capturar imagen de camara cedula entrada peatonal"
            )
        return self.build_capture_response(
            result,
            "Error al capturar imagen de camara cedula entrada peatonal",
            include_data_url,
            include_image
        )
    
    def capture_usuario_entrada_peatonal(
        self,
        include_data_url: bool = False,
        include_image: bool = True,
        response_mode: str = "json"
    ):
        """Captura imagen de usuario entrada peatonal (192.168.1.224)"""
        # Evita I/O a disco para respuestas JSON: ya tenemos bytes en memoria.
        save_file = False
        result = capture_usuario_entrada_peatonal(self.output_dir, save_file=save_file)
        if response_mode.lower() == "jpeg":
            return self.build_capture_jpeg_response(
                result,
                "Error al capturar imagen de camara usuario entrada peatonal"
            )
        return self.build_capture_response(
            result,
            "Error al capturar imagen de camara usuario entrada peatonal",
            include_data_url,
            include_image
        )
