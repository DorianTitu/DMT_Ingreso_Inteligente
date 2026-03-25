# Sistema de Almacenamiento de Registros Vehiculares

## Descripción General

Este sistema automáticamente:
1. **Crea la estructura de carpetas** con formato: `YEAR/MES/DÍA/TICKET_#####`
2. **Guarda las imágenes** (cedula.jpg, usuario.jpg, placa.jpg) en cada carpeta de ticket
3. **Actualiza un Excel maestro** con todos los datos del registro
4. **Genera números de ticket** secuenciales automáticos

## Estructura de Carpetas

```
C:\Users\LENOVO\Documents\Base de datos\DMT_Gestion_Ingreso\Ingreso Vehicular\
├── 2026/
│   ├── 01_Enero/
│   │   ├── 15/
│   │   │   ├── TICKET_000001/
│   │   │   │   ├── cedula.jpg
│   │   │   │   ├── usuario.jpg
│   │   │   │   └── placa.jpg
│   │   │   └── TICKET_000002/
│   │   │       ├── cedula.jpg
│   │   │       ├── usuario.jpg
│   │   │       └── placa.jpg
│   │   └── 16/
│   └── 02_Febrero/
└── registro_historico_vehiculos.xlsx
```

## Archivo Excel (registro_historico_vehiculos.xlsx)

| Número de Ticket | Nombres | Apellidos | Cédula | Hora de Ingreso | Hora de Salida | Departamento | Motivo | Fecha de Registro |
|---|---|---|---|---|---|---|---|---|
| TICKET_000001 | Juan | Pérez | 1234567890 | 14:30:45 | | Administración | Visita | 2026-01-15 14:30:45 |
| TICKET_000002 | María | González | 0987654321 | 14:35:12 | 15:45:30 | Contabilidad | Reunión | 2026-01-15 14:35:12 |

## Configuración

### 1. Establecer la Ruta Base

En **Windows**, antes de ejecutar la API:

```bash
# Command Prompt (cmd) - Una sola línea o en .bat
set REGISTRO_VEHICULAR_PATH=C:\Users\LENOVO\Documents\Base de datos\DMT_Gestion_Ingreso\Ingreso Vehicular

# PowerShell
$env:REGISTRO_VEHICULAR_PATH="C:\Users\LENOVO\Documents\Base de datos\DMT_Gestion_Ingreso\Ingreso Vehicular"
```

O permanentemente agregando a variables de entorno del sistema.

### 2. Para Desarrollo Local

```bash
# Usa la ruta relativa por defecto
# Los registros se guardarán en ./registros_vehiculares
python api/main.py
```

## Uso de la API

### POST `/save/registro_vehicular`

Guarda un registro completo de ingreso vehicular.

**Payload (JSON):**

```json
{
  "nombres": "Juan",
  "apellidos": "Pérez García",
  "cedula": "1234567890",
  "departamento": "Administración",
  "motivo": "Visita",
  "imagen_cedula_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "imagen_usuario_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "imagen_placa_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "hora_ingreso": "14:30:45"
}
```

**Respuesta Exitosa (200):**

```json
{
  "success": true,
  "numero_ticket": 1,
  "codigo_ticket": "TICKET_000001",
  "ruta_ticket": "C:/Users/LENOVO/Documents/Base de datos/DMT_Gestion_Ingreso/Ingreso Vehicular/2026/01_Enero/15/TICKET_000001",
  "imagenes_guardadas": {
    "cedula": "C:/Users/LENOVO/Documents/Base de datos/DMT_Gestion_Ingreso/Ingreso Vehicular/2026/01_Enero/15/TICKET_000001/cedula.jpg",
    "usuario": "C:/Users/LENOVO/Documents/Base de datos/DMT_Gestion_Ingreso/Ingreso Vehicular/2026/01_Enero/15/TICKET_000001/usuario.jpg",
    "placa": "C:/Users/LENOVO/Documents/Base de datos/DMT_Gestion_Ingreso/Ingreso Vehicular/2026/01_Enero/15/TICKET_000001/placa.jpg"
  },
  "mensaje": "Registro TICKET_000001 guardado exitosamente"
}
```

## Flujo Completo desde el Frontend

1. **Capturar imágenes**
   ```
   POST /capture/camara_cedula_entrada_vehicular
   POST /capture/camara_usuario_entrada_vehicular
   POST /capture/camara_placa_entrada_vehicular
   ```
   → Obtiene las imágenes en base64

2. **Extractar datos (OCR)**
   - Frontend envía imagen de cédula a módulo OCR
   - Obtiene: nombres, apellidos, cédula

3. **Llenar formulario**
   - Usuario completa: Departamento, Motivo
   - Sistema rellena automáticamente: Nombres, Apellidos, Cédula (del OCR)

4. **Guardar registro**
   ```
   POST /save/registro_vehicular
   ```
   → Crea carpeta, guarda imágenes, actualiza Excel

5. **Registrar salida** (opcional)
   - cuando el vehículo se va, actualizar la hora de salida en Excel

## Módulo Python: `registro_vehicular.py`

### Clase: `RegistroVehicular`

```python
from registro_vehicular import RegistroVehicular

# Inicializar
registro = RegistroVehicular("C:/ruta/base")

# Guardar un registro
resultado = registro.guardar_registro({
    'nombres': 'Juan',
    'apellidos': 'Pérez',
    'cedula': '1234567890',
    'departamento': 'Admin',
    'motivo': 'Visita',
    'imagen_cedula_base64': '...',
    'imagen_usuario_base64': '...',
    'imagen_placa_base64': '...',
    'hora_ingreso': '14:30:45'
})

# Resultado
print(resultado['numero_ticket'])  # 1
print(resultado['ruta_ticket'])    # C:/ruta/base/2026/01_Enero/15/TICKET_000001

# Actualizar hora de salida
registro.actualizar_hora_salida(numero_ticket=1, hora_salida='15:45:30')
```

## Notas Importantes

1. **Números de Ticket**: Se incrementan secuencialmente basados en el número de registros en el Excel
2. **Fechas Automáticas**: Se usa la fecha actual del servidor (year/mes/día)
3. **Meses en Español**: Enero, Febrero, Marzo, ... Diciembre
4. **Imágenes Opcionales**: Puedes enviar solo las imágenes que tengas disponibles
5. **Excel**: Se crea automáticamente si no existe, con formatos y estilos listos
6. **Atomicidad**: Cada operación completa se realiza o falla completamente

## Troubleshooting

### Error: "El sistema de registro no está inicializado"
- Asegúrate que la variable de entorno REGISTRO_VEHICULAR_PATH está configurada
- Reinicia la API después de configurar la variable

### Error: "Permiso denegado" en Windows
- Verifica que la ruta existe y tienes permisos de lectura/escritura
- En algunos casos, debes usar `C:/` en lugar de `C:\`

### Excel bloqueado o en uso
- No dejes el archivo Excel abierto en Excel mientras usas la API
- La API necesita exclusividad de escritura en el archivo

## Seguridad

- Las rutas se normalizan automáticamente para compatibilidad cross-platform
- Las imágenes se guardan con validación de base64
- El Excel se guarda con encriptación básica (opcional)
