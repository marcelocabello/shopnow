from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(
    title="Departamento de Clientes - ShopNow",
    description="Servicio encargado de la custodia y registro oficial de los clientes de la empresa.",
    version="1.1.0",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

# Definición del Contrato (Esquema de datos)
class Cliente(BaseModel):
    id_cliente: int = Field(..., description="ID único numérico del cliente", example=101)
    nombre: str = Field(..., description="Nombre completo del ciudadano/cliente", example="Juan Pérez", min_length=3, max_length=100)
    correo: str = Field(..., description="Correo electrónico institucional o personal", example="juan@ejemplo.com")

# Base de datos en memoria (Simulando el departamento)
db_clientes = []

@app.get("/clientes", response_model=List[Cliente],
        summary="Obtener lista de clientes registrados",
        description="Este endpoint devuelve la lista completa de clientes registrados en el sistema. No requiere parámetros.",
        tags=["Operaciones de Lectura"],
        responses={
            200: {
                "description": "Lista de clientes obtenida exitosamente",
                "content": {
                    "application/json": {
                        "example": [
                            {"id_cliente": 101, "nombre": "Juan Pérez", "correo": "juan@ejemplo.com"}
                        ]
                    }
                }
            },
            400: {
                "description": "Error al obtener la lista de clientes",
                "content": {
                    "application/json": {
                        "example": {"error": "No se pudieron obtener los clientes"}
                    }
                }
            }
        }
    )    

def obtener_clientes():
    return db_clientes

@app.post("/clientes", summary="Registrar nuevo cliente", tags=["Operaciones de Escritura"])
def registrar_cliente(nuevo_cliente: Cliente):
    """
    Este endpoint permite el ingreso de un nuevo cliente al sistema. 
    **Requisito:** El JSON debe cumplir estrictamente con el formato oficial.
    """
    return {"mensaje": "Cliente registrado exitosamente", "datos": nuevo_cliente}
