"""
API FastAPI para captura de cámaras ONVIF-Dahua
Endpoints para capturar imágenes de las 3 cámaras
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
import base64
from datetime import datetime
from sqlalchemy.orm import Session

from camera_capture import capture_camera1, capture_camera3, capture_camera250
from database import init_db, get_db, Persona, Captura
from ocr_processor import ocr_processor

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
    """Inicializar BD y crear directorios"""
    init_db()
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
async def capture_integrada(db: Session = Depends(get_db)):
    """
    Captura integrada de las 3 cámaras:
    1. Captura imagen de placa
    2. Captura imagen de usuario
    3. Captura imagen de cédula y extrae OCR
    4. Verifica si la persona existe en BD
    5. Guarda registro en BD
    6. Devuelve imágenes en base64
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
        
        # Extraer número de cédula con OCR
        cedula_numero = ocr_processor.extraer_numero_cedula(result_cedula['file'])
        
        if not cedula_numero:
            raise HTTPException(
                status_code=400,
                detail="No se pudo extraer número de cédula"
            )
        
        # Convertir imágenes a base64
        with open(result_placa['file'], 'rb') as f:
            placa_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        with open(result_usuario['file'], 'rb') as f:
            usuario_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        with open(result_cedula['file'], 'rb') as f:
            cedula_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        # Verificar si la persona existe
        persona = db.query(Persona).filter(Persona.cedula_numero == cedula_numero).first()
        
        if not persona:
            persona = Persona(cedula_numero=cedula_numero)
            db.add(persona)
            db.commit()
            db.refresh(persona)
        
        # Guardar captura en BD (sin rutas de archivo)
        captura = Captura(
            persona_id=persona.id,
            ruta_imagen_cedula=result_cedula['file'],
            ruta_imagen_usuario=result_usuario['file'],
            ruta_imagen_placa=result_placa['file']
        )
        db.add(captura)
        db.commit()
        db.refresh(captura)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "cedula_numero": cedula_numero,
                "persona_id": persona.id,
                "captura_id": captura.id,
                "imagenes": {
                    "placa_base64": placa_b64,
                    "usuario_base64": usuario_b64,
                    "cedula_base64": cedula_b64
                },
                "mensaje": "Captura integrada completada exitosamente"
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
async def capture_camera250_endpoint():
    """
    Captura imagen de Camera250 (192.168.1.250)
    Protocolo: RTSP
    Descripción: Cedula entrada vehicular
    """
    result = capture_camera250(OUTPUT_DIR)
    
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

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("INICIANDO API DE CAPTURA DE CAMARAS")
    print("=" * 60)
    print("\nAcceder a: http://localhost:8000")
    print("Documentacion: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
