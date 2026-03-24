#!/usr/bin/env python3
"""
Script de prueba para OCR - sin usar API
Extrae y muestra exactamente qué está viendo el OCR
"""

import sys
sys.path.insert(0, '/Users/doriantituana/Desktop/Proyectos/Producto/Ejercicio')

from ocr_processor import ocr_processor

# Usar la imagen más reciente
imagen = '/Users/doriantituana/Desktop/Proyectos/Producto/Ejercicio/snapshots_camaras/camara_cedula_entrada_vehicular_20260322_135704.jpg'

print("=" * 80)
print("PRUEBA DE OCR DIRECTA")
print("=" * 80)
print(f"\nImagen: {imagen}\n")

# Extraer datos
resultado = ocr_processor.extraer_datos_cedula(imagen)

print("\n" + "=" * 80)
print("RESULTADO FINAL:")
print("=" * 80)
print(f"NUI: {resultado['nui']}")
print(f"Nombres: {resultado['nombres']}")
print(f"Apellidos: {resultado['apellidos']}")
print("=" * 80)
