# Camera Capture API - Aplicación Dockerizada

## Requisitos

- Docker
- Docker Compose (opcional pero recomendado)

## Estructura del Proyecto

```
.
├── Dockerfile              # Configuración de imagen Docker
├── docker-compose.yml      # Orquestación de contenedores
├── .dockerignore           # Archivos a excluir en build
├── requirements.txt        # Dependencias de Python
├── api/
│   └── main.py            # Aplicación FastAPI
├── camera_capture/
│   ├── camara_cedula_entrada_vehicular.py
│   ├── camara_placa_entrada_vehicular.py
│   └── camara_usuario_entrada_vehicular.py
└── snapshots_camaras/     # Directorio de salida (volumen)
```

## Ejecución con Docker Compose (Recomendado)

### 1. Construir la imagen

```bash
docker-compose build
```

### 2. Iniciar la aplicación

```bash
docker-compose up -d
```

### 3. Ver logs

```bash
docker-compose logs -f api
```

### 4. Detener la aplicación

```bash
docker-compose down
```

## Ejecución con Docker (Manual)

### 1. Construir la imagen

```bash
docker build -t cedula-camera-api:latest .
```

### 2. Ejecutar el contenedor

```bash
docker run -d \
  --name cedula-camera-api \
  -p 8000:8000 \
  -v $(pwd)/snapshots_camaras:/app/snapshots_camaras \
  cedula-camera-api:latest
```

### 3. Ver logs

```bash
docker logs -f cedula-camera-api
```

### 4. Detener el contenedor

```bash
docker stop cedula-camera-api
docker rm cedula-camera-api
```

## Acceso a la API

Una vez que el contenedor esté corriendo:

- **API REST**: http://localhost:8000
- **Documentación Swagger**: http://localhost:8000/docs
- **Documentación ReDoc**: http://localhost:8000/redoc

## Endpoints Disponibles

### 1. Health Check
```bash
GET /health
```

### 2. Captura de Cámara de Placa
```bash
POST /capture/camara_placa_entrada_vehicular
```
Retorna imagen en base64 de Camera1 (Placa entrada vehicular)

### 3. Captura de Cámara de Usuario
```bash
POST /capture/camara_usuario_entrada_vehicular
```
Retorna imagen en base64 de Camera3 (Usuario entrada vehicular)

### 4. Captura de Cámara de Cédula
```bash
POST /capture/camara_cedula_entrada_vehicular
```
Retorna imagen en base64 de Camera250 (Cédula entrada vehicular)

## Cámaras Configuradas

| Cámara | IP | Protocolo | Modelo | Ubicación |
|--------|----|-----------| ------|-----------|
| Camera1 | 192.168.1.10 | HTTP Digest | Dahua | Placa entrada vehicular |
| Camera3 | 192.168.1.3 | RTSP | Dahua | Usuario entrada vehicular |
| Camera250 | 192.168.1.250 | RTSP | Dahua | Cédula entrada vehicular |

## Volúmenes

- `./snapshots_camaras:/app/snapshots_camaras` - Directorio donde se guardan las capturas de las cámaras

## Variables de Entorno

- `PYTHONUNBUFFERED=1` - Desactiva el buffer de salida de Python (para logs en tiempo real)

## Troubleshooting

### La aplicación no puede conectarse a las cámaras

Verifica que:
1. Las direcciones IP de las cámaras sean correctas
2. Las cámaras estén en la misma red que el contenedor Docker
3. Las credenciales de autenticación sean correctas (modifica en los archivos de captura)

### Puerto 8000 ya está en uso

```bash
# Usa un puerto diferente en docker-compose.yml
ports:
  - "8080:8000"  # Puerto local:puerto contenedor
```

O elimina el contenedor anterior:
```bash
docker-compose down
```

### Volumen de snapshots no persiste

Asegúrate que el volumen esté correctamente montado:
```bash
docker inspect cedula-camera-api | grep -A 5 Mounts
```

