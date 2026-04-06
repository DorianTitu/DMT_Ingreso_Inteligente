"""
Esquemas Pydantic - Capa de presentación
DTOs para requests/responses
"""

from .vehicular import RegistroVehicularRequest
from .peatonal import RegistroPeaonalRequest
from .common import HoraSalidaRequest, CedulaOCRRequest

__all__ = [
    'RegistroVehicularRequest',
    'RegistroPeaonalRequest',
    'HoraSalidaRequest',
    'CedulaOCRRequest',
]
