"""
API FastAPI para captura de cámaras ONVIF-Dahua
Endpoints para capturar imágenes de las 3 cámaras
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import os
import base64
from typing import Callable

from camera_capture import (
    capture_camera1, 
    capture_camera3, 
    capture_camera250
)

# Crear aplicación FastAPI
app = FastAPI(
    title="Camera Capture API",
    description="API para capturar imágenes de cámaras Dahua ONVIF",
    version="1.0.0"
)

OUTPUT_DIR = "snapshots_camaras"

# ============ FUNCIONES AUXILIARES ============

def image_to_base64(file_path: str) -> str:
    """Convertir imagen a base64"""
    with open(file_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def build_capture_response(result: dict, error_prefix: str) -> JSONResponse:
    """Arma una respuesta uniforme para todos los endpoints de captura."""
    if not result.get('success'):
        raise HTTPException(
            status_code=500,
            detail=f"{error_prefix}: {result.get('error', 'Desconocido')}"
        )

    image_base64 = image_to_base64(result['file'])
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "camera": result['camera'],
            "ip": result['ip'],
            "file": result['file'],
            "size_bytes": result['size'],
            "image_base64": image_base64,
            "message": "Captura exitosa"
        }
    )

@app.on_event("startup")
async def startup_event():
    """Crear directorios necesarios"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "nombre": "Camera Capture API",
        "version": "1.0.0",
        "descripcion": "API para capturar imágenes de cámaras Dahua ONVIF",
        "endpoints": {
            "/capture/camara_placa_entrada_vehicular": "Capturar imagen de Camera1",
            "/capture/camara_usuario_entrada_vehicular": "Capturar imagen de Camera3",
            "/capture/camara_cedula_entrada_vehicular": "Capturar imagen de Camera250",
            "/health": "Estado de salud de la API"
        }
    }

@app.get("/health")
async def health():
    """Verificar estado de la API"""
    return {"status": "OK", "message": "API funcionando correctamente"}

@app.post("/capture/camara_placa_entrada_vehicular")
async def capture_camera1_endpoint():
    """
    Captura imagen de Camera1 (192.168.1.108)
    Protocolo: HTTP Digest
    Descripción: Placa entrada vehicular
    """
    result = capture_camera1(OUTPUT_DIR)
    return build_capture_response(result, f"Error al capturar imagen de {result.get('camera', 'Camera1 (Placa)')}")

@app.post("/capture/camara_usuario_entrada_vehicular")
async def capture_camera3_endpoint():
    """
    Captura imagen de Camera3 (192.168.1.223)
    Protocolo: RTSP
    Descripción: Usuario entrada vehicular
    """
    result = capture_camera3(OUTPUT_DIR)
    return build_capture_response(result, f"Error al capturar imagen de {result.get('camera', 'Camera3 (Usuario)')}")

@app.post("/capture/camara_cedula_entrada_vehicular")
async def capture_cedula_endpoint():
    """
    Captura imagen de la cédula
    - Captura desde Camera250 (cédula entrada vehicular)
    - Retorna imagen en base64
    """
    result = capture_camera250(OUTPUT_DIR)
    return build_capture_response(result, "Error en captura")

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("INICIANDO API DE CAPTURA DE CAMARAS")
    print("=" * 60)
    print("\nAcceder a: http://localhost:8000")
    print("Documentacion: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
