#!/usr/bin/env python
"""
Script de prueba para verificar que el sistema de registro peatonal funciona.
"""

import sys
import os
from pathlib import Path

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registro_peatonal import RegistroPeatonal

# Ruta base para prueba
ruta_base = r'C:\Users\LENOVO\Documents\Base de datos\DMT_Gestion_Ingreso\Ingreso Peatonal'

print("=" * 60)
print("PRUEBA DEL SISTEMA DE REGISTRO PEATONAL")
print("=" * 60)

# Inicializar el sistema
print(f"\n1️⃣ Inicializando RegistroPeatonal en: {ruta_base}")
try:
    registro = RegistroPeatonal(ruta_base)
    print("   ✅ RegistroPeatonal inicializado correctamente")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Prueba 1: Guardar un registro de prueba
print("\n2️⃣ Guardando un registro de prueba...")
try:
    datos_prueba = {
        'persona': 'MARTIN ALEXANDER SIMBAÑA LIMA',
        'cedula': '1721931226',
        'departamento': 'Administración',
        'imagen_cedula_base64': None,
        'imagen_usuario_base64': None,
        'hora_ingreso': '14:30:45'
    }
    
    resultado = registro.guardar_registro(datos_prueba)
    
    if resultado['success']:
        print(f"   ✅ Registro guardado exitosamente")
        ticket_num = resultado['numero_ticket']
        print(f"   📌 Ticket: TICKET_{ticket_num:06d}")
        print(f"   📁 Ruta: {resultado['ruta_ticket']}")
    else:
        print(f"   ❌ Error: {resultado.get('error', 'Desconocido')}")
        sys.exit(1)
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Prueba 2: Obtener todos los tickets
print("\n3️⃣ Obteniendo todos los tickets...")
try:
    resultado = registro.obtener_todos_tickets()
    
    if resultado['success']:
        print(f"   ✅ Se encontraron {resultado['cantidad']} tickets")
        for ticket in resultado['tickets'][-3:]:  # Mostrar últimos 3
            print(f"      - {ticket['ticket']}: {ticket['persona']} ({ticket['cedula']})")
    else:
        print(f"   ❌ Error: {resultado.get('error', 'Desconocido')}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Prueba 3: Actualizar hora de salida
print("\n4️⃣ Actualizando hora de salida...")
try:
    resultado = registro.actualizar_hora_salida_por_ticket('1', '16:45:30')
    
    if resultado['success']:
        print(f"   ✅ Hora de salida actualizada")
        print(f"   📌 Ticket: {resultado['ticket']}")
        print(f"   ⏰ Hora salida: {resultado['hora_salida']}")
    else:
        print(f"   ⚠️ No se pudo actualizar: {resultado.get('error', 'Desconocido')}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Prueba 4: Obtener fotos de un ticket
print("\n5️⃣ Obteniendo fotos del ticket...")
try:
    resultado = registro.obtener_fotos_ticket(1)
    
    if resultado['success']:
        print(f"   ✅ Ticket encontrado")
        print(f"   📁 Ruta: {resultado['ruta_ticket']}")
        print(f"   📷 Imágenes: {len(resultado['imagenes'])} archivo(s)")
    else:
        print(f"   ℹ️ {resultado.get('error', 'Desconocido')}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("PRUEBA COMPLETADA")
print("=" * 60)
