from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(
    title="Departamento de Pedidos - ShopNow",
    description="Responsable de coordinar la venta final entre clientes y productos.",
    version="1.0.0"
)

# Definición del Contrato de Servicio
class Pedido(BaseModel):
    id_pedido: int = Field(..., example=501)
    id_cliente: int = Field(..., description="ID del cliente que compra", example=101)
    id_producto: int = Field(..., description="ID del producto solicitado", example=1)
    cantidad: int = Field(..., gt=0, example=2)

db_pedidos = []

@app.post("/pedidos", summary="Registrar un nuevo pedido", tags=["Operaciones"])
def crear_pedido(nuevo_p: Pedido):
    """
    REGLA DE ORO: Por hoy, el departamento es autónomo y confía en el formato.
    Aprenderemos a consultar a los otros departamentos.
    
    Este endpoint permite el ingreso de un nuevo pedido al sistema. 
    **Requisito:** El JSON debe cumplir estrictamente con el formato oficial.
    """
    db_pedidos.append(nuevo_p)
    return {"mensaje": "Pedido recibido y en proceso de coordinación", "datos": nuevo_p}

@app.get("/pedidos", response_model=List[Pedido], summary="Listar todos los pedidos", tags=["Consultas"])
def listar_pedidos():
    return db_pedidos
