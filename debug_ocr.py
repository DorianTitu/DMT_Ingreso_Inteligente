#!/usr/bin/env python3
"""Debug script para probar OCR"""
import os
import sys
from ocr_processor import ocr_processor

# Obtener última imagen capturada
archivos = sorted([f for f in os.listdir('snapshots_camaras') if 'cedula' in f], reverse=True)

if archivos:
    imagen = os.path.join('snapshots_camaras', archivos[0])
    print(f'[DEBUG] Probando con: {imagen}')
    print(f'[DEBUG] Tamaño: {os.path.getsize(imagen) / 1024:.1f} KB')
    print('[DEBUG] Iniciando OCR...')
    
    resultado = ocr_processor.extraer_datos_cedula(imagen)
    
    print(f'[DEBUG] Resultado: {resultado}')
else:
    print('[ERROR] No hay imágenes de cédula')
    sys.exit(1)
