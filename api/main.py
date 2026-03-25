"""
API FastAPI para captura de cámaras ONVIF-Dahua
Endpoints para capturar imágenes de las 3 cámaras y guardar registros
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
import base64
import sys
import tempfile
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

from camera_capture import (
    capture_camera1, 
    capture_camera3, 
    capture_camera250
)
from camera_capture.camara_cedula_entrada_vehicular import warmup_cedula_ocr_reader

# Agregar el directorio padre al path para importar registro_vehicular
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import registro_vehicular

# Crear aplicación FastAPI
app = FastAPI(
    title="Camera Capture API",
    description="API para capturar imágenes de cámaras Dahua ONVIF",
    version="1.0.0"
)

OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "dmt_capture_tmp")

# ============ MODELOS PYDANTIC ============

class RegistroVehicularRequest(BaseModel):
    """Modelo para guardar un registro vehicular completo"""
    nombres: str
    apellidos: str
    cedula: str
    departamento: str
    motivo: str
    imagen_cedula_base64: Optional[str] = None
    imagen_usuario_base64: Optional[str] = None
    imagen_placa_base64: Optional[str] = None
    hora_ingreso: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "nombres": "Juan",
                "apellidos": "Pérez",
                "cedula": "1234567890",
                "departamento": "Administración",
                "motivo": "Visita",
                "imagen_cedula_base64": "base64_string...",
                "imagen_usuario_base64": "base64_string...",
                "imagen_placa_base64": "base64_string...",
                "hora_ingreso": "14:30:45"
            }
        }


class HoraSalidaRequest(BaseModel):
    """Modelo para actualizar hora de salida por ticket."""
    ticket: str
    hora_salida: Optional[str] = None

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

    captured_file = result['file']
    image_base64 = image_to_base64(captured_file)

    temp_file_removed = False
    if captured_file and os.path.exists(captured_file):
        try:
            os.remove(captured_file)
            temp_file_removed = True
        except OSError:
            temp_file_removed = False

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
            "ocr_data": result.get('ocr_data'),
            "ocr_error": result.get('ocr_error'),
            "timings": result.get('timings'),
            "message": "Captura exitosa"
        }
    )

@app.on_event("startup")
async def startup_event():
    """Crear directorios necesarios e inicializar registro manager"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Obtener ruta base desde .env o usar ruta relativa como fallback
    ruta_base = os.environ.get(
        'REGISTRO_VEHICULAR_PATH',
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'registros_vehiculares')
    )
    
    print(f"📁 Ruta de registros: {ruta_base}")
    registro_vehicular.inicializar_registro_manager(ruta_base)

    try:
        warmup_cedula_ocr_reader()
        print("[OCR] EasyOCR precargado correctamente")
    except Exception as exc:
        print(f"[OCR] No se pudo precargar EasyOCR: {exc}")

@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "nombre": "Camera Capture API",
        "version": "1.0.0",
        "descripcion": "API para capturar imágenes de cámaras Dahua ONVIF y guardar registros",
        "endpoints": {
            "capture": {
                "/capture/camara_placa_entrada_vehicular": "Capturar imagen de Camera1",
                "/capture/camara_usuario_entrada_vehicular": "Capturar imagen de Camera3",
                "/capture/camara_cedula_entrada_vehicular": "Capturar imagen de Camera250"
            },
            "registro": {
                "/save/registro_vehicular": "Guardar registro completo de ingreso vehicular",
                "/get/registro_vehicular": "Listar todos los tickets desde el Excel",
                "/update/hora_salida": "Actualizar hora de salida por ticket"
            },
            "salud": {
                "/health": "Estado de salud de la API"
            }
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

@app.post("/save/registro_vehicular")
async def save_registro_vehicular(registro: RegistroVehicularRequest):
    """
    Guarda un registro completo de ingreso vehicular
    - Crea la estructura de carpetas (YEAR/MES/DIA/TICKET_#####)
    - Guarda las imágenes en la carpeta del ticket
    - Actualiza el Excel maestro
    
    Retorna:
    {
        "success": true,
        "numero_ticket": 42,
        "mensaje": "Registro TICKET_000042 guardado exitosamente",
        "ruta_ticket": "C:/ruta/2026/01_Enero/15/TICKET_000042"
    }
    """
    if registro_vehicular.registro_manager is None:
        raise HTTPException(
            status_code=500,
            detail="El sistema de registro no está inicializado"
        )
    
    try:
        # Preparar datos
        datos = {
            'nombres': registro.nombres,
            'apellidos': registro.apellidos,
            'cedula': registro.cedula,
            'departamento': registro.departamento,
            'motivo': registro.motivo,
            'imagen_cedula_base64': registro.imagen_cedula_base64,
            'imagen_usuario_base64': registro.imagen_usuario_base64,
            'imagen_placa_base64': registro.imagen_placa_base64,
            'hora_ingreso': registro.hora_ingreso
        }
        
        # Guardar registro
        resultado = registro_vehicular.registro_manager.guardar_registro(datos)
        
        if resultado.get('success'):
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "numero_ticket": resultado['numero_ticket'],
                    "codigo_ticket": f"TICKET_{resultado['numero_ticket']:06d}",
                    "ruta_ticket": resultado['ruta_ticket'],
                    "imagenes_guardadas": resultado['imagenes'],
                    "mensaje": resultado['mensaje']
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error al guardar registro: {resultado.get('error', 'Desconocido')}"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando registro: {str(e)}"
        )


@app.get("/get/registro_vehicular")
async def get_registro_vehicular():
    """Lista todos los tickets del Excel maestro de ingreso vehicular."""
    if registro_vehicular.registro_manager is None:
        raise HTTPException(
            status_code=500,
            detail="El sistema de registro no está inicializado"
        )

    resultado = registro_vehicular.registro_manager.obtener_todos_tickets()
    if not resultado.get('success'):
        raise HTTPException(
            status_code=500,
            detail=f"Error leyendo tickets: {resultado.get('error', 'Desconocido')}"
        )

    return JSONResponse(
        status_code=200,
        content={
            'success': True,
            'total': resultado.get('total', 0),
            'tickets': resultado.get('tickets', []),
        }
    )


@app.post("/update/hora_salida")
async def update_hora_salida(payload: HoraSalidaRequest):
    """Actualiza hora de salida usando número o código de ticket."""
    if registro_vehicular.registro_manager is None:
        raise HTTPException(
            status_code=500,
            detail="El sistema de registro no está inicializado"
        )

    resultado = registro_vehicular.registro_manager.actualizar_hora_salida_por_ticket(
        payload.ticket,
        payload.hora_salida
    )

    if not resultado.get('success'):
        detalle = resultado.get('error', 'Desconocido')
        status_code = 404 if 'No se encontró el ticket' in detalle else 400
        raise HTTPException(status_code=status_code, detail=detalle)

    return JSONResponse(
        status_code=200,
        content={
            'success': True,
            'ticket': resultado.get('ticket'),
            'hora_salida': resultado.get('hora_salida'),
            'mensaje': resultado.get('mensaje')
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("INICIANDO API DE CAPTURA DE CAMARAS")
    print("=" * 60)
    print("\nAcceder a: http://localhost:8000")
    print("Documentacion: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
