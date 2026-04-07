"""
Rutas de captura de cámaras
"""

from fastapi import APIRouter
from app.services.servicio_captura import ServicioCaptura
from app.services.servicio_ocr import ServicioOCR
from app.schemas.common import CedulaOCRRequest

router = APIRouter(tags=["Captura"])

# Servicios globales (se inicializan en main.py)
camera_service: ServicioCaptura = None
ocr_service: ServicioOCR = None


def set_services(camera_svc: ServicioCaptura, ocr_svc: ServicioOCR):
    """Inyecta servicios en las rutas"""
    global camera_service, ocr_service
    camera_service = camera_svc
    ocr_service = ocr_svc
    ocr_service = ocr_svc


# ============ CAPTURA VEHICULAR ============

@router.get("/capture/camara_placa_entrada_vehicular")
async def capture_placa_entrada_vehicular(
    include_data_url: bool = False,
    include_image: bool = True,
    response_mode: str = "json"
):
    """
    Captura imagen de Camera1 (192.168.1.108)
    Protocolo: HTTP Digest
    Descripción: Placa entrada vehicular
    """
    return camera_service.capture_placa_entrada_vehicular(
        include_data_url, include_image, response_mode
    )


@router.get("/capture/camara_usuario_entrada_vehicular")
async def capture_usuario_entrada_vehicular(
    include_data_url: bool = False,
    include_image: bool = True,
    response_mode: str = "json"
):
    """
    Captura imagen de usuario entrada vehicular (Camera3, 192.168.1.224)
    Protocolo: HTTP Digest
    """
    return camera_service.capture_usuario_entrada_vehicular(
        include_data_url, include_image, response_mode
    )


@router.get("/capture/camara_cedula_entrada_vehicular")
async def capture_cedula_entrada_vehicular(
    include_data_url: bool = False,
    include_image: bool = True,
    response_mode: str = "json",
    draw_boxes: bool = False,
):
    """
    Captura imagen de la cédula (sin OCR)
    - Captura desde Camera250 (cédula entrada vehicular)
    - Retorna imagen en base64
    """
    return camera_service.capture_cedula_entrada_vehicular(
        include_data_url=include_data_url,
        include_image=include_image,
        response_mode=response_mode,
        draw_boxes=draw_boxes,
    )


# ============ CAPTURA PEATONAL ============

@router.get("/capture/camara_cedula_entrada_peatonal")
async def capture_cedula_entrada_peatonal(
    include_data_url: bool = False,
    include_image: bool = True,
    response_mode: str = "json"
):
    """
    Captura imagen de cámara cédula entrada peatonal
    - IP: 192.168.1.3
    - Protocolo: HTTP Digest
    """
    return camera_service.capture_cedula_entrada_peatonal(
        include_data_url, include_image, response_mode
    )


@router.get("/capture/camara_usuario_entrada_peatonal")
async def capture_usuario_entrada_peatonal(
    include_data_url: bool = False,
    include_image: bool = True,
    response_mode: str = "json"
):
    """
    Captura imagen de usuario entrada peatonal (192.168.1.224)
    Protocolo: HTTP Digest
    """
    return camera_service.capture_usuario_entrada_peatonal(
        include_data_url, include_image, response_mode
    )


# ============ OCR ============

@router.get("/extract/camara_cedula_entrada_vehicular")
async def extract_cedula_data_get(imagen_cedula_base64: str):
    """
    Extrae datos OCR de una imagen de cédula enviada en base64
    - Entrada: imagen_cedula_base64 (query parameter)
    - Salida: cedula, nombres, apellidos y tiempos de OCR
    """
    return ocr_service.extract_cedula_from_base64(imagen_cedula_base64)


@router.post("/extract/camara_cedula_entrada_vehicular")
async def extract_cedula_data_post(payload: CedulaOCRRequest):
    """
    Extrae datos OCR de una imagen de cédula enviada en JSON
    - Entrada: {"imagen_cedula_base64": "..."}
    - Recomendado para evitar errores de longitud/encoding en query string
    """
    return ocr_service.extract_cedula_from_base64(payload.imagen_cedula_base64)


@router.get("/extract/camara_cedula_entrada_vehicular/live")
async def extract_cedula_data_live(
    include_data_url: bool = False,
    include_image: bool = True,
    draw_boxes: bool = True,
):
    """
    Captura cédula desde la cámara vehicular y ejecuta OCR en servidor.
    - No requiere enviar base64 desde cliente.
    """
    return camera_service.capture_cedula_entrada_vehicular(
        include_data_url=include_data_url,
        include_image=include_image,
        response_mode="json",
        do_ocr=True,
        draw_boxes=draw_boxes,
    )
