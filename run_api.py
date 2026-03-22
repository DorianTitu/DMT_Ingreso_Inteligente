#!/usr/bin/env python3
"""
Script para ejecutar la API FastAPI
"""

import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.main import app
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("INICIANDO API DE CAPTURA DE CAMARAS")
    print("=" * 60)
    print("\nAcceder a: http://localhost:8000")
    print("Documentacion: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
