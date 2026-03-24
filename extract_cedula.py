#!/usr/bin/env python3
"""
Extrae información de cédula de la imagen usando OCR
"""

from PIL import Image
import easyocr
import re
import time

image_path = "/Users/doriantituana/Desktop/Proyectos/Producto/Ejercicio/snapshots_camaras/camara_cedula_entrada_vehicular_20260322_161952.jpg"

tiempo_inicio = time.time()

try:
    # Abrir imagen
    img = Image.open(image_path)
    print(f"📸 Imagen cargada")
    print(f"   Tamaño: {img.size}")
    
    # Aplicar OCR con EasyOCR
    print("\n🔍 Extrayendo texto con OCR...")
    tiempo_ocr_inicio = time.time()
    
    reader = easyocr.Reader(['es'], gpu=False)
    results = reader.readtext(str(image_path))
    
    tiempo_ocr_fin = time.time()
    tiempo_ocr = tiempo_ocr_fin - tiempo_ocr_inicio
    
    # Extraer todo el texto
    texto_completo = "\n".join([text[1] for text in results])
    
    print(f"\n⏱️  Tiempo de OCR: {tiempo_ocr:.2f} segundos")
    
    print("\n📄 Texto extraído:\n")
    print(texto_completo)
    
    print("\n" + "="*60)
    print("ANÁLISIS DE DATOS EXTRAÍDOS")
    print("="*60)
    
    # Buscar patrones de NUI, Apellidos, Nombres
    lineas = texto_completo.split('\n')
    
    nui = None
    apellidos = None
    nombres = None
    
    print("\nLíneas procesadas:")
    for i, linea in enumerate(lineas):
        linea_limpia = linea.strip()
        if linea_limpia:
            print(f"  {i}: {linea_limpia}")
    
    tiempo_final = time.time()
    tiempo_total = tiempo_final - tiempo_inicio
    
    print("\n" + "="*60)
    print("⏱️  TIEMPO TOTAL")
    print("="*60)
    print(f"Tiempo OCR:    {tiempo_ocr:.2f} segundos")
    print(f"Tiempo Total:  {tiempo_total:.2f} segundos")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
