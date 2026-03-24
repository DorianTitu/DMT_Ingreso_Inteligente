#!/usr/bin/env python3
"""
Script de prueba: Integración de captura + OCR de cédula
Demuestra cómo usar la nueva función capturar_y_extraer_cedula()
"""

import json
from camera_capture import capturar_y_extraer_cedula, extraer_datos_cedula

def test_extraer_datos_existentes():
    """
    Prueba: Extraer datos de una imagen de cédula existente
    Sin necesidad de capturar nueva foto
    """
    print("\n" + "=" * 70)
    print("TEST 1: Extraer datos de imagen existente")
    print("=" * 70)
    
    resultado = extraer_datos_cedula(
        "snapshots_camaras/camara_cedula_entrada_vehicular_20260322_161952.jpg"
    )
    
    if resultado['success']:
        print(f"\n✅ Extracción exitosa")
        print(f"   NUI:        {resultado.get('nui')}")
        print(f"   Apellidos:  {resultado.get('apellidos')}")
        print(f"   Nombres:    {resultado.get('nombres')}")
        print(f"   Tiempo OCR: {resultado.get('tiempo_ocr')} segundos")
        print(f"\n📄 Texto completo extraído:")
        print(f"   {resultado.get('texto_completo')}")
    else:
        print(f"❌ Error: {resultado.get('error')}")
    
    return resultado

def test_captura_y_extraccion():
    """
    Prueba: Capturar imagen de DVR Y extraer datos en una sola llamada
    Nota: Requiere que Camera250 esté disponible
    """
    print("\n" + "=" * 70)
    print("TEST 2: Capturar Y extraer en una llamada")
    print("=" * 70)
    
    print("\n⏳ Capturando imagen de Camera250...")
    print("⏳ Ejecutando OCR...")
    
    resultado = capturar_y_extraer_cedula()
    
    if resultado['success']:
        print(f"\n✅ Captura y extracción exitosa")
        
        # Datos de captura
        captura = resultado.get('captura', {})
        print(f"\n📸 Captura:")
        print(f"   Cámara:     {captura.get('camera')}")
        print(f"   IP:         {captura.get('ip')}")
        print(f"   Archivo:    {captura.get('file')}")
        print(f"   Tamaño:     {captura.get('size')} bytes")
        
        # Datos de cédula
        cedula = resultado.get('cedula')
        if cedula:
            print(f"\n🆔 Cédula (OCR):")
            print(f"   NUI:        {cedula.get('nui')}")
            print(f"   Apellidos:  {cedula.get('apellidos')}")
            print(f"   Nombres:    {cedula.get('nombres')}")
            print(f"   Tiempo OCR: {cedula.get('tiempo_ocr')} segundos")
        else:
            print(f"\n⚠️ Sin datos de cédula")
    else:
        print(f"❌ Error: {resultado.get('error')}")
    
    return resultado

if __name__ == "__main__":
    print("\n" + "🚀" * 35)
    print("PRUEBA DE INTEGRACIÓN: Captura + OCR de Cédula")
    print("🚀" * 35)
    
    # Test 1: Extraer de imagen existente
    test1 = test_extraer_datos_existentes()
    
    # Test 2: Capturar y extraer (comentado si no tienes cámara disponible)
    # test2 = test_captura_y_extraccion()
    
    print("\n" + "=" * 70)
    print("✅ PRUEBAS COMPLETADAS")
    print("=" * 70)
    print("\n📚 Funciones disponibles:")
    print("   • extraer_datos_cedula(ruta_imagen)")
    print("   • capturar_y_extraer_cedula(output_dir)")
    print("\n🔗 Endpoints disponibles en API:")
    print("   POST /capture/camara_cedula_entrada_vehicular")
    print("\n")
