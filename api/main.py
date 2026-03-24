"""
API FastAPI para captura de cámaras ONVIF-Dahua
Endpoints para capturar imágenes de las 3 cámaras
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import base64
from datetime import datetime

from camera_capture import (
    capture_camera1, 
    capture_camera3, 
    capture_camera250,
    capturar_y_extraer_cedula,
    extraer_datos_cedula
)
from ocr_processor import ocr_processor
from data_storage import DataStorage

# ============ MODELOS PYDANTIC ============

class SaveCedulaRequest(BaseModel):
    """Modelo para solicitud de guardado de datos de cédula"""
    storage_path: str
    nui: str
    apellidos: str
    nombres: str
    tiempo_ocr: float = None
    texto_completo: str = None
    imagen_cedula: str = None
    imagen_placa: str = None
    imagen_usuario: str = None

class CaptureAndSaveRequest(BaseModel):
    """Modelo para capturar y guardar automáticamente"""
    storage_path: str

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
            "/capture/integrada": "Capturar 3 imágenes, extraer OCR y guardar en BD",
            "/capture/camara_placa_entrada_vehicular": "Capturar imagen de Camera1",
            "/capture/camara_usuario_entrada_vehicular": "Capturar imagen de Camera3",
            "/capture/camara_cedula_entrada_vehicular": "Capturar imagen de Camera250",
            "/capture/all": "Capturar imágenes de todas las cámaras",
            "/health": "Estado de salud de la API"
        }
    }

@app.get("/health")
async def health():
    """Verificar estado de la API"""
    return {"status": "OK", "message": "API funcionando correctamente"}

@app.post("/capture/integrada")
async def capture_integrada():
    """
    Captura integrada de las 3 cámaras:
    1. Captura imagen de placa
    2. Captura imagen de usuario
    3. Captura imagen de cédula y extrae OCR
    4. Devuelve imágenes en base64 + datos de cédula
    """
    try:
        # Capturar las 3 imágenes
        result_placa = capture_camera1(OUTPUT_DIR)
        result_usuario = capture_camera3(OUTPUT_DIR)
        result_cedula = capture_camera250(OUTPUT_DIR)
        
        if not (result_placa['success'] and result_usuario['success'] and result_cedula['success']):
            raise HTTPException(
                status_code=500,
                detail="Error capturando imágenes"
            )
        
        # Recortar imagen de cédula
        ocr_processor._recortar_imagen(result_cedula['file'])
        
        # Extraer datos de cédula con OCR
        datos_cedula = ocr_processor.extraer_datos_cedula(result_cedula['file'])
        nui = datos_cedula.get('nui')
        nombres = datos_cedula.get('nombres')
        apellidos = datos_cedula.get('apellidos')
        
        # Convertir imágenes a base64
        with open(result_placa['file'], 'rb') as f:
            placa_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        with open(result_usuario['file'], 'rb') as f:
            usuario_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        with open(result_cedula['file'], 'rb') as f:
            cedula_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "datos_cedula": {
                    "nui": nui,
                    "nombres": nombres,
                    "apellidos": apellidos
                },
                "imagenes": {
                    "placa": {
                        "file": result_placa['file'],
                        "size_bytes": result_placa['size'],
                        "base64": placa_b64
                    },
                    "usuario": {
                        "file": result_usuario['file'],
                        "size_bytes": result_usuario['size'],
                        "base64": usuario_b64
                    },
                    "cedula": {
                        "file": result_cedula['file'],
                        "size_bytes": result_cedula['size'],
                        "base64": cedula_b64
                    }
                },
                "mensaje": "Captura integrada exitosa"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en captura integrada: {str(e)}"
        )

@app.post("/capture/camara_placa_entrada_vehicular")
async def capture_camera1_endpoint():
    """
    Captura imagen de Camera1 (192.168.1.108)
    Protocolo: HTTP Digest
    Descripción: Placa entrada vehicular
    """
    result = capture_camera1(OUTPUT_DIR)
    
    if result['success']:
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
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Error al capturar imagen de {result['camera']}: {result.get('error', 'Desconocido')}"
        )

@app.post("/capture/camara_usuario_entrada_vehicular")
async def capture_camera3_endpoint():
    """
    Captura imagen de Camera3 (192.168.1.223)
    Protocolo: RTSP
    Descripción: Usuario entrada vehicular
    """
    result = capture_camera3(OUTPUT_DIR)
    
    if result['success']:
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
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Error al capturar imagen de {result['camera']}: {result.get('error', 'Desconocido')}"
        )

@app.post("/capture/camara_cedula_entrada_vehicular")
async def capture_cedula_endpoint():
    """
    Captura imagen de la cédula y extrae datos con OCR automáticamente:
    - Captura desde Camera250 (cédula entrada vehicular)
    - Extrae NUI, apellidos, nombres usando OCR
    - Retorna imagen en base64 + datos extraídos
    - Incluye métrica de tiempo de procesamiento OCR
    """
    try:
        # Capturar Y extraer en una sola llamada integrada
        resultado = capturar_y_extraer_cedula(OUTPUT_DIR)
        
        if not resultado['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Error en captura: {resultado.get('error', 'Desconocido')}"
            )
        
        # Convertir imagen a base64
        image_base64 = image_to_base64(resultado['captura']['file'])
        
        # Preparar respuesta con datos de cédula
        datos_cedula = resultado.get('cedula', {})
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "captura": {
                    "camera": resultado['captura']['camera'],
                    "ip": resultado['captura']['ip'],
                    "file": resultado['captura']['file'],
                    "size_bytes": resultado['captura']['size'],
                    "image_base64": image_base64
                },
                "cedula": {
                    "nui": datos_cedula.get('nui'),
                    "apellidos": datos_cedula.get('apellidos'),
                    "nombres": datos_cedula.get('nombres'),
                    "tiempo_ocr_segundos": datos_cedula.get('tiempo_ocr'),
                    "texto_completo": datos_cedula.get('texto_completo')
                } if datos_cedula else None,
                "mensaje": "Captura y análisis OCR exitoso"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en captura de cédula: {str(e)}"
        )

@app.post("/capture/all")
async def capture_all_cameras():
    """Captura imágenes de todas las 3 cámaras simultáneamente"""
    results = []
    success_count = 0
    
    # Capturar de camera1
    result1 = capture_camera1(OUTPUT_DIR)
    if result1['success']:
        result1['image_base64'] = image_to_base64(result1['file'])
        success_count += 1
    results.append(result1)
    
    # Capturar de camera3
    result3 = capture_camera3(OUTPUT_DIR)
    if result3['success']:
        result3['image_base64'] = image_to_base64(result3['file'])
        success_count += 1
    results.append(result3)
    
    # Capturar de camera250
    result250 = capture_camera250(OUTPUT_DIR)
    if result250['success']:
        result250['image_base64'] = image_to_base64(result250['file'])
        success_count += 1
    results.append(result250)
    
    return JSONResponse(
        status_code=200 if success_count > 0 else 500,
        content={
            "success": success_count == 3,
            "total_cameras": 3,
            "successful": success_count,
            "failed": 3 - success_count,
            "details": [
                {
                    "camera": r['camera'],
                    "ip": r['ip'],
                    "success": r['success'],
                    "file": r['file'],
                    "size_bytes": r['size'],
                    "image_base64": r.get('image_base64', None),
                    "error": r.get('error', None)
                } for r in results
            ]
        }
    )

@app.get("/snapshots")
async def list_snapshots():
    """Listar todas las fotos capturadas"""
    if not os.path.exists(OUTPUT_DIR):
        return {"snapshots": [], "total": 0}
    
    snapshots = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.jpg')]
    snapshots.sort(reverse=True)
    
    return {
        "snapshots": snapshots,
        "total": len(snapshots),
        "directory": OUTPUT_DIR
    }

# ============ ENDPOINTS DE ALMACENAMIENTO ============

@app.post("/storage/save-cedula-data")
async def save_cedula_data(request: SaveCedulaRequest):
    """
    Guarda los datos de una cédula en CSV en la ruta especificada
    
    Body (JSON):
    {
        "storage_path": "/ruta/donde/guardar",
        "nui": "1754756920",
        "apellidos": "SIMBAÑA LIMA",
        "nombres": "MARTIN ALEXANDER",
        "tiempo_ocr": 0.46,
        "texto_completo": "...",
        "imagen_cedula": "/ruta/imagen.jpg"
    }
    """
    try:
        # Crear instancia de almacenamiento con la ruta especificada
        storage = DataStorage(request.storage_path)
        
        # Preparar datos de cédula
        cedula_data = {
            'nui': request.nui,
            'apellidos': request.apellidos,
            'nombres': request.nombres,
            'tiempo_ocr': request.tiempo_ocr,
            'texto_completo': request.texto_completo
        }
        
        # Preparar rutas de imágenes
        imagen_paths = {
            'cedula': request.imagen_cedula,
            'placa': request.imagen_placa,
            'usuario': request.imagen_usuario
        }
        
        # Guardar en CSV
        resultado = storage.save_cedula_data(cedula_data, imagen_paths)
        
        if resultado['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Datos guardados exitosamente",
                    "storage_path": request.storage_path,
                    "csv_file": resultado['csv_file'],
                    "timestamp": resultado['timestamp']
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error guardando datos: {resultado.get('error')}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en almacenamiento: {str(e)}"
        )

@app.post("/storage/capture-and-save")
async def capture_and_save(request: CaptureAndSaveRequest):
    """
    Captura imagen de cédula, extrae datos OCR Y los guarda automáticamente
    en la ruta especificada
    
    Body (JSON):
    {
        "storage_path": "/ruta/donde/guardar"
    }
    
    Proceso automático:
    1. Captura de Camera250
    2. Extracción de datos con OCR
    3. Guardado en CSV en la ruta especificada
    """
    try:
        # Capturar y extraer
        resultado_captura = capturar_y_extraer_cedula(OUTPUT_DIR)
        
        if not resultado_captura['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Error en captura: {resultado_captura.get('error')}"
            )
        
        # Preparar datos para almacenar
        datos_cedula = resultado_captura.get('cedula', {})
        captura_info = resultado_captura.get('captura', {})
        
        cedula_data = {
            'nui': datos_cedula.get('nui'),
            'apellidos': datos_cedula.get('apellidos'),
            'nombres': datos_cedula.get('nombres'),
            'tiempo_ocr': datos_cedula.get('tiempo_ocr'),
            'texto_completo': datos_cedula.get('texto_completo')
        }
        
        imagen_paths = {
            'cedula': captura_info.get('file')
        }
        
        # Guardar en CSV
        storage = DataStorage(request.storage_path)
        resultado_guardado = storage.save_cedula_data(cedula_data, imagen_paths)
        
        if resultado_guardado['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Captura y almacenamiento exitoso",
                    "storage_path": request.storage_path,
                    "csv_file": resultado_guardado['csv_file'],
                    "captura": {
                        "file": captura_info.get('file'),
                        "camera": captura_info.get('camera'),
                        "ip": captura_info.get('ip'),
                        "size_bytes": captura_info.get('size')
                    },
                    "cedula": {
                        "nui": datos_cedula.get('nui'),
                        "apellidos": datos_cedula.get('apellidos'),
                        "nombres": datos_cedula.get('nombres'),
                        "tiempo_ocr_segundos": datos_cedula.get('tiempo_ocr')
                    }
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error guardando datos: {resultado_guardado.get('error')}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en captura y almacenamiento: {str(e)}"
        )

@app.get("/storage/info")
async def storage_info(storage_path: str):
    """
    Obtiene información sobre el almacenamiento en una ruta específica
    
    Query params:
    - storage_path: Ruta del almacenamiento
    
    Ejemplo: /storage/info?storage_path=/Users/dorian/data
    """
    try:
        storage = DataStorage(storage_path)
        info = storage.get_storage_info()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "storage_info": info
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo información: {str(e)}"
        )

@app.get("/storage/records")
async def get_records(storage_path: str):
    """
    Obtiene todos los registros guardados en una ruta específica
    
    Query params:
    - storage_path: Ruta del almacenamiento
    
    Ejemplo: /storage/records?storage_path=/Users/dorian/data
    """
    try:
        storage = DataStorage(storage_path)
        resultado = storage.get_all_records()
        
        if resultado['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "total_registros": resultado['total'],
                    "registros": resultado['records']
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=resultado.get('error')
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo registros: {str(e)}"
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
