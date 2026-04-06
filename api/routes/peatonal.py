"""
Rutas para ingreso peatonal
"""

from fastapi import APIRouter
from app.schemas.peatonal import RegistroPeaonalRequest
from app.schemas.common import HoraSalidaRequest, ActualizarRegistroPeaonalRequest
from app.services.servicio_peatonal import ServicioPeatonal

router = APIRouter(tags=["Ingreso Peatonal"])

# Servicio global (se inicializa en main.py)
peatonal_service: ServicioPeatonal = None


def set_service(svc: ServicioPeatonal):
    """Inyecta servicio en las rutas"""
    global peatonal_service
    peatonal_service = svc


@router.post("/save/registro_peatonal")
async def save_registro_peatonal(registro: RegistroPeaonalRequest):
    """
    Guarda un registro completo de ingreso peatonal
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
    return peatonal_service.guardar_registro(registro)
    return peatonal_service.guardar_registro(registro)


@router.get("/get/registro_peatonal")
async def get_registro_peatonal():
    """Lista todos los tickets del Excel maestro de ingreso peatonal"""
    return peatonal_service.obtener_todos_tickets()


@router.get("/get/fotos_ticket_peatonal/{ticket}")
async def get_fotos_ticket_peatonal(ticket: str):
    """Obtiene las fotos guardadas (cedula/usuario) para un ticket de peatón"""
    return peatonal_service.obtener_fotos_ticket(ticket)


@router.get("/get/ticket_info_peatonal/{ticket}")
async def get_ticket_info_peatonal(ticket: str):
    """
    Obtiene toda la información del ticket peatonal + fotos
    - Retorna: dados completos (nombre, apellido, cedula, departamento, motivo, etc)
    - Retorna: todas las fotos disponibles (cedula, usuario)
    """
    return peatonal_service.obtener_informacion_completa_ticket(ticket)


@router.put("/update/hora_salida_peatonal")
async def update_hora_salida_peatonal(payload: HoraSalidaRequest):
    """Actualiza hora de salida de un peatón usando número o código de ticket"""
    return peatonal_service.actualizar_hora_salida(payload.ticket, payload.hora_salida)


@router.put("/edit/registro_peatonal")
async def edit_registro_peatonal(actualizacion: ActualizarRegistroPeaonalRequest):
    """
    Edita datos de un registro peatonal existente
    
    Campos editables:
    - nombre
    - apellido
    - cedula
    - departamento
    - motivo
    - observaciones
    
    Solo envía los campos que deseas actualizar (el resto se ignoran)
    """
    return peatonal_service.actualizar_registro(actualizacion)
    return peatonal_service.actualizar_registro(actualizacion)
