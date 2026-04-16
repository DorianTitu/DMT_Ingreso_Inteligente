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

from camera_capture.camara_placa_entrada_vehicular import capture_camera1
from camera_capture.camara_usuario_entrada_peatonal import (
    capture_camera250 as capture_usuario_entrada_peatonal,
)
from camera_capture.camara_usuario_entrada_vehicular import capture_camera3 as capture_usuario_entrada_vehicular
from camera_capture.camara_cedula_entrada_peatonal import (
    capture_cedula_entrada_peatonal,
)
from camera_capture.camara_cedula_entrada_vehicular import capture_camera250
from app.services.ocr_cedulas import get_peatonal_ocr, get_vehicular_ocr


class ServicioCaptura:
    """Servicio encargado de capturar imágenes de cámaras"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.vehicular_ocr = get_vehicular_ocr()
        self.peatonal_ocr = get_peatonal_ocr()
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
                "ocr_data": result.get('ocr_data'),
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
    ):
        """Captura imagen de cédula entrada vehicular (Camera250)"""
        result = capture_camera250(self.output_dir, save_file=False)

        if result.get('success') and (do_ocr or draw_boxes):
            image_bytes = self._extract_image_bytes(result)
            ocr_data = None
            ocr_error = None

            try:
                ocr_data = self.vehicular_ocr.analyze(image_bytes)
            except Exception as exc:
                ocr_error = str(exc)

            if draw_boxes and ocr_error is None:
                boxed_bytes, crop_boxes = self.vehicular_ocr.draw_boxes(image_bytes, ocr_data)
                if boxed_bytes:
                    result['image_bytes'] = boxed_bytes
                if crop_boxes is not None:
                    result['crop_boxes'] = crop_boxes
                    result['ocr_boxes_preview'] = crop_boxes

            if do_ocr:
                result['ocr_data'] = ocr_data
                result['ocr_error'] = ocr_error

                if isinstance(ocr_data, dict) and isinstance(ocr_data.get('tiempos_ms'), dict):
                    timings = result.get('timings') or {}
                    ocr_timings = ocr_data['tiempos_ms']
                    timings['crop_ms'] = ocr_timings.get('crop_ms')
                    timings['crop_ok'] = ocr_timings.get('crop_ok')
                    timings['ocr_ms'] = ocr_timings.get('ocr_ms')
                    result['timings'] = timings

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
            image_bytes = self._extract_image_bytes(result)
            ocr_data = None
            ocr_error = None
            try:
                ocr_data = self.peatonal_ocr.analyze(image_bytes)
            except Exception as exc:
                ocr_error = str(exc)

            if ocr_error is None:
                boxed_bytes, crop_boxes = self.peatonal_ocr.draw_boxes(image_bytes, ocr_data)
                if boxed_bytes:
                    result['image_bytes'] = boxed_bytes
                if crop_boxes is not None:
                    result['crop_boxes'] = crop_boxes

            result['ocr_data'] = ocr_data
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
        result = capture_usuario_entrada_peatonal(self.output_dir)
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
