"""
Rutas para ingreso vehicular
"""

from fastapi import APIRouter
from app.schemas.vehicular import RegistroVehicularRequest
from app.schemas.common import HoraSalidaRequest, ActualizarRegistroVehicularRequest
from app.services.servicio_vehicular import ServicioVehicular

router = APIRouter(tags=["Ingreso Vehicular"])

# Servicio global (se inicializa en main.py)
vehicular_service: ServicioVehicular = None


def set_service(svc: ServicioVehicular):
    """Inyecta servicio en las rutas"""
    global vehicular_service
    vehicular_service = svc


@router.post("/save/registro_vehicular")
async def save_registro_vehicular(registro: RegistroVehicularRequest):
    """
    Guarda un registro completo de ingreso vehicular
    - Crea la estructura de carpetas (YEAR/MES/DIA/TICKET_#####)
    - Guarda las imágenes en la carpeta del ticket
    - Actualiza el Excel maestro
    
    Retorna:
    {
        "success": true,
        "numero_ticket": 42,
        "mensaje": "Registro TICKET_000042 guardado exitosamente"
    }
    """
    return vehicular_service.guardar_registro(registro)


@router.get("/get/registro_vehicular")
async def get_registro_vehicular():
    """Lista todos los tickets del Excel maestro de ingreso vehicular"""
    return vehicular_service.obtener_todos_tickets()


@router.get("/get/fotos_ticket/{ticket}")
async def get_fotos_ticket(ticket: str):
    """Obtiene las fotos guardadas (cedula/usuario/placa) para un ticket"""
    return vehicular_service.obtener_fotos_ticket(ticket)


@router.get("/get/ticket_info/{ticket}")
async def get_ticket_info(ticket: str):
    """
    Obtiene toda la información del ticket + fotos
    - Retorna: datos completos (nombres, apellidos, cedula, departamento, motivo, etc)
    - Retorna: todas las fotos disponibles (cedula, usuario, placa)
    """
    return vehicular_service.obtener_informacion_completa_ticket(ticket)


@router.put("/update/hora_salida")
async def update_hora_salida(payload: HoraSalidaRequest):
    """Actualiza hora de salida usando número o código de ticket"""
    return vehicular_service.actualizar_hora_salida(payload.ticket, payload.hora_salida)


@router.put("/edit/registro_vehicular")
async def edit_registro_vehicular(actualizacion: ActualizarRegistroVehicularRequest):
    """
    Edita datos de un registro vehicular existente
    
    Campos editables:
    - nombres
    - apellidos
    - cedula
    - departamento
    - motivo
    - observaciones
    
    Solo envía los campos que deseas actualizar (el resto se ignoran)
    """
    return vehicular_service.actualizar_registro(actualizacion)
