"""
Routes - Endpoints de la API
"""

from .vehicular import router as vehicular_router
from .peatonal import router as peatonal_router
from .captura import router as captura_router
from .salud import router as salud_router

__all__ = [
    'vehicular_router',
    'peatonal_router',
    'captura_router',
    'salud_router',
]
