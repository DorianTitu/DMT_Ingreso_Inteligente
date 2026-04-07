"""
Rutas de salud / información
"""

from fastapi import APIRouter

router = APIRouter(tags=["Salud"])


@router.get("/health")
async def health():
    """Verificar estado de la API"""
    return {"status": "OK", "message": "API funcionando correctamente"}


@router.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "nombre": "Camera Capture API",
        "version": "1.0.0",
        "descripcion": "API para capturar imágenes de cámaras Dahua ONVIF y guardar registros",
        "endpoints": {
            "capture": {
                "/capture/camara_placa_entrada_vehicular": "Capturar imagen de Camera1 (placa vehicular)",
                "/capture/camara_usuario_entrada_vehicular": "Capturar imagen de Camera3 (usuario vehicular, 192.168.1.224)",
                "/capture/camara_cedula_entrada_vehicular": "Capturar imagen de Camera250 (cédula vehicular, sin OCR)",
                "/capture/camara_cedula_entrada_peatonal": "Capturar imagen de cámara cédula entrada peatonal (192.168.1.3, con OCR)",
                "/capture/camara_usuario_entrada_peatonal": "Capturar imagen de usuario entrada peatonal (192.168.1.224, alias)"
            },
            "ocr": {
                "/extract/camara_cedula_entrada_vehicular [GET]": "Extraer datos OCR de una imagen base64 enviada por query string",
                "/extract/camara_cedula_entrada_vehicular [POST]": "Extraer datos OCR de una imagen base64 enviada en JSON (recomendado)",
                "/extract/camara_cedula_entrada_vehicular/live": "Capturar cédula vehicular desde cámara y ejecutar OCR en servidor"
            },
            "registro_vehicular": {
                "/save/registro_vehicular": "Guardar registro completo de ingreso vehicular",
                "/get/registro_vehicular": "Listar todos los tickets vehiculares desde el Excel",
                "/get/fotos_ticket/{ticket}": "Obtener fotos guardadas por ticket vehicular",
                "/update/hora_salida": "Actualizar hora de salida vehicular por ticket"
            },
            "registro_peatonal": {
                "/save/registro_peatonal": "Guardar registro completo de ingreso peatonal",
                "/get/registro_peatonal": "Listar todos los tickets peatonales desde el Excel",
                "/get/fotos_ticket_peatonal/{ticket}": "Obtener fotos guardadas por ticket peatonal",
                "/update/hora_salida_peatonal": "Actualizar hora de salida peatonal por ticket"
            },
            "salud": {
                "/health": "Estado de salud de la API"
            }
        }
    }
