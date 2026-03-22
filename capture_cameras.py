#!/usr/bin/env python3
"""
Sistema de captura de cámaras ONVIF-Dahua (Script Standalone)
Captura fotos de múltiples cámaras y las guarda con timestamp

Cámaras soportadas:
- Camera1 (192.168.1.108): HTTP snapshot + autenticación digest
- Camera3 (192.168.1.223): RTSP
- Camera250 (192.168.1.250): RTSP

NOTA: Este script utiliza los módulos refactorizados en camera_capture/
Para usar la API REST, ejecuta: python run_api.py
"""

import os
from datetime import datetime

# Importar funciones de captura de cada módulo
from camera_capture import capture_camera1, capture_camera3, capture_camera250

# ============ CONFIGURACIÓN ============
OUTPUT_DIR = "snapshots_camaras"

def main():
    """Función principal"""
    print("=" * 50)
    print("CAPTURA DE CAMARAS ONVIF-DAHUA")
    print("=" * 50 + "\n")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    success_count = 0
    cameras_config = [
        ("Camera1 (Placa)", capture_camera1),
        ("Camera3 (Usuario)", capture_camera3),
        ("Camera250 (Cedula)", capture_camera250)
    ]
    
    for camera_name, capture_func in cameras_config:
        print(f"{camera_name}...", end=" ", flush=True)
        result = capture_func(OUTPUT_DIR)
        
        if result['success']:
            print(f"OK ({result['size']:,} bytes)")
            success_count += 1
        else:
            print(f"ERRO ({result.get('error', 'Desconocido')})")
    
    total_count = len(cameras_config)
    
    print(f"\n{'=' * 50}")
    print(f"Captura completada: {success_count}/{total_count} camaras")
    print(f"Fotos guardadas en: {OUTPUT_DIR}/")
    print(f"{'=' * 50}\n")

if __name__ == "__main__":
    main()
