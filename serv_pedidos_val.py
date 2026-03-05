import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(
    title="Departamento de Pedidos - ShopNow",
    description="Responsable de coordinar la venta final entre clientes y productos.",
    version="1.0.1"
)

# Definición del Contrato de Servicio
class Pedido(BaseModel):
    id_pedido: int = Field(..., example=501)
    id_cliente: int = Field(..., description="ID del cliente que compra", example=101)
    id_producto: int = Field(..., description="ID del producto solicitado", example=1)
    cantidad: int = Field(..., gt=0, example=2)

db_pedidos = []

# URLs de los otros departamentos (Ventanillas)
URL_CLIENTES = "http://127.0.0.1:8001/clientes"
URL_PRODUCTOS = "http://127.0.0.1:8002/productos"

@app.post("/pedidos", tags=["Operaciones"])
def crear_pedido(p: Pedido):
    # 1. VALIDAR CLIENTE (Sesión 12)
    try:
        res_c = requests.get(URL_CLIENTES)
        # Buscamos si el ID existe en la lista que nos dio el otro departamento
        if not any(c['id_cliente'] == p.id_cliente for c in res_c.json()):
            raise HTTPException(status_code=400, detail="Error de Negocio: El cliente no existe")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="El Departamento de Clientes no está disponible")

    # 2. VALIDAR PRODUCTO (Sesión 13)
    try:
        res_p = requests.get(URL_PRODUCTOS)
        if not any(prod['id_producto'] == p.id_producto for prod in res_p.json()):
            raise HTTPException(status_code=400, detail="Error de Negocio: El producto no existe")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="El Departamento de Productos no está disponible")

    # Si todo es válido, guardamos
    db_pedidos.append(p)
    return {"mensaje": "Pedido validado y registrado exitosamente"}

@app.get("/pedidos", response_model=List[Pedido], summary="Listar todos los pedidos", tags=["Consultas"])
def listar_pedidos():
    return db_pedidos
