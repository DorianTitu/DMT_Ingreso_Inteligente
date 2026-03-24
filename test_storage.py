#!/usr/bin/env python3
"""
Prueba de almacenamiento de datos de cédulas
Demuestra cómo guardar datos en CSV con rutas configurables
"""

from data_storage import DataStorage
import json

def test_almacenamiento_basico():
    """Test 1: Guardar datos básicos en CSV"""
    print("\n" + "=" * 70)
    print("TEST 1: Almacenamiento básico en CSV")
    print("=" * 70)
    
    # Definir ruta de almacenamiento
    storage_path = "/tmp/cedulas_test"
    print(f"📁 Ruta de almacenamiento: {storage_path}")
    
    # Crear instancia de almacenamiento
    storage = DataStorage(storage_path)
    
    # Datos de cédula a guardar
    cedula_data = {
        'nui': '1754756920',
        'apellidos': 'SIMBAÑA LIMA',
        'nombres': 'MARTIN ALEXANDER',
        'tiempo_ocr': 0.46,
        'texto_completo': 'Datos extraídos del OCR'
    }
    
    # Guardar
    resultado = storage.save_cedula_data(cedula_data)
    
    if resultado['success']:
        print(f"\n✅ Datos guardados exitosamente")
        print(f"   Archivo: {resultado['csv_file']}")
        print(f"   Timestamp: {resultado['timestamp']}")
    else:
        print(f"❌ Error: {resultado.get('error')}")
    
    return storage_path

def test_informacion_almacenamiento(storage_path):
    """Test 2: Obtener información de almacenamiento"""
    print("\n" + "=" * 70)
    print("TEST 2: Información de almacenamiento")
    print("=" * 70)
    
    storage = DataStorage(storage_path)
    info = storage.get_storage_info()
    
    print(f"\n📊 Información:")
    print(f"   Ruta: {info['storage_path']}")
    print(f"   Archivo CSV: {info['csv_file']}")
    print(f"   Archivo existe: {info['archivo_existe']}")
    
    if info['archivo_existe']:
        print(f"   Tamaño: {info['tamaño_bytes']} bytes")
        print(f"   Total registros: {info['total_registros']}")

def test_leer_registros(storage_path):
    """Test 3: Leer registros del CSV"""
    print("\n" + "=" * 70)
    print("TEST 3: Leer registros del CSV")
    print("=" * 70)
    
    storage = DataStorage(storage_path)
    resultado = storage.get_all_records()
    
    if resultado['success']:
        print(f"\n📋 Total registros: {resultado['total']}")
        
        if resultado['total'] > 0:
            print(f"\n📝 Registros guardados:")
            for i, record in enumerate(resultado['records'], 1):
                print(f"\n   Registro {i}:")
                print(f"      Timestamp: {record.get('timestamp')}")
                print(f"      NUI: {record.get('nui')}")
                print(f"      Apellidos: {record.get('apellidos')}")
                print(f"      Nombres: {record.get('nombres')}")
                print(f"      Tiempo OCR: {record.get('tiempo_ocr_segundos')} seg")
    else:
        print(f"❌ Error: {resultado.get('error')}")

def test_multiples_registros(storage_path):
    """Test 4: Guardar múltiples registros"""
    print("\n" + "=" * 70)
    print("TEST 4: Guardar múltiples registros")
    print("=" * 70)
    
    storage = DataStorage(storage_path)
    
    # Multiple cedulas a guardar
    cedulas = [
        {
            'nui': '1754756920',
            'apellidos': 'SIMBAÑA LIMA',
            'nombres': 'MARTIN ALEXANDER',
            'tiempo_ocr': 0.46
        },
        {
            'nui': '1800234567',
            'apellidos': 'PEREZ GARCIA',
            'nombres': 'JUAN CARLOS',
            'tiempo_ocr': 0.52
        },
        {
            'nui': '1900345678',
            'apellidos': 'MENDOZA TORRES',
            'nombres': 'ANA MARIA',
            'tiempo_ocr': 0.49
        }
    ]
    
    print(f"\n📝 Guardando {len(cedulas)} registros...")
    resultado = storage.save_multiple_cedulas(cedulas)
    
    if resultado['success']:
        print(f"✅ Guardados {resultado['registros_guardados']} registros")
        print(f"   Archivo: {resultado['csv_file']}")
    else:
        print(f"❌ Error: {resultado.get('error')}")
    
    # Leer nuevamente
    print(f"\n📋 Verificando...")
    info = storage.get_storage_info()
    print(f"   Total de registros ahora: {info['total_registros']}")

if __name__ == "__main__":
    print("\n" + "🚀" * 35)
    print("PRUEBA DE ALMACENAMIENTO DE CÉDULAS EN CSV")
    print("🚀" * 35)
    
    # Test 1: Almacenamiento básico
    storage_path = test_almacenamiento_basico()
    
    # Test 2: Información
    test_informacion_almacenamiento(storage_path)
    
    # Test 3: Leer registros
    test_leer_registros(storage_path)
    
    # Test 4: Múltiples registros
    test_multiples_registros(storage_path)
    
    print("\n" + "=" * 70)
    print("✅ PRUEBAS COMPLETADAS")
    print("=" * 70)
    
    print("\n📚 Endpoints disponibles en API:")
    print("   POST /storage/save-cedula-data")
    print("        → Guardar datos de cédula en ruta especificada")
    print("\n   POST /storage/capture-and-save")
    print("        → Capturar + extraer OCR + guardar automáticamente")
    print("\n   GET /storage/info?storage_path=/ruta")
    print("        → Obtener información de almacenamiento")
    print("\n   GET /storage/records?storage_path=/ruta")
    print("        → Obtener todos los registros guardados")
    print("\n")
