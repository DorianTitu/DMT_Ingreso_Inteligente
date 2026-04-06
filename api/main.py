"""
API FastAPI refactorizada con arquitectura de capas
Integración de servicios, repositorios y rutas
"""

import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configuración
from app.config import (
    API_TITLE, API_DESCRIPTION, API_VERSION,
    OUTPUT_DIR, REGISTRO_VEHICULAR_PATH, REGISTRO_PEATONAL_PATH
)

# Servicios
from app.services.servicio_captura import ServicioCaptura
from app.services.servicio_ocr import ServicioOCR
from app.services.servicio_vehicular import ServicioVehicular
from app.services.servicio_peatonal import ServicioPeatonal

# Rutas
from api.routes import salud_router, captura_router, vehicular_router, peatonal_router
from api import routes as routes_module

# Importar managers de registro
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import registro_vehicular
import registro_peatonal


# ============ CREAR APLICACIÓN FASTAPI ============

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION
)

# Agregar CORS si es necesario
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ INICIALIZACIÓN DE SERVICIOS ============

# Servicios globales
camera_service: ServicioCaptura = None
ocr_service: ServicioOCR = None
vehicular_service: ServicioVehicular = None
peatonal_service: ServicioPeatonal = None



@app.on_event("startup")
async def startup_event():
    """Inicialización de servicios y managers"""
    global camera_service, ocr_service, vehicular_service, peatonal_service
    
    print("=" * 60)
    print("INICIANDO API DE CAPTURA DE CAMARAS")
    print("=" * 60)
    
    # Crear directorios
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # ============ INICIALIZAR MANAGERS DE REGISTRO ============
    
    print(f"📁 Ruta de registros vehiculares: {REGISTRO_VEHICULAR_PATH}")
    registro_vehicular.inicializar_registro_manager(REGISTRO_VEHICULAR_PATH)
    
    print(f"📁 Ruta de registros peatonales: {REGISTRO_PEATONAL_PATH}")
    registro_peatonal.inicializar_registro_manager(REGISTRO_PEATONAL_PATH)
    
    # ============ INICIALIZAR SERVICIOS ============
    
    # Servicio de captura
    camera_service = ServicioCaptura(OUTPUT_DIR)
    
    # Servicio OCR
    ocr_service = ServicioOCR()
    ocr_service.warmup_ocr()
    
    # Servicio vehicular
    vehicular_service = ServicioVehicular(registro_vehicular.registro_manager)
    
    # Servicio peatonal
    peatonal_service = ServicioPeatonal(registro_peatonal.registro_manager)
    
    # ============ INYECTAR SERVICIOS EN RUTAS ============
    
    routes_module.captura.set_services(camera_service, ocr_service)
    routes_module.vehicular.set_service(vehicular_service)
    routes_module.peatonal.set_service(peatonal_service)
    
    print("\n✅ Todos los servicios inicializados correctamente")
    print("=" * 60)
    print(f"Acceder a: http://localhost:8000")
    print(f"Documentacion: http://localhost:8000/docs")
    print("=" * 60 + "\n")


# ============ REGISTRAR RUTAS ============

app.include_router(salud_router)
app.include_router(captura_router)
app.include_router(vehicular_router)
app.include_router(peatonal_router)


# ============ MANEJO DE ERRORES ============

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Manejo global de excepciones"""
    return {
        "error": str(exc),
        "detail": "Error interno del servidor"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
