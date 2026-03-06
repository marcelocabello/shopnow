import csv
import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(
    title="Coordinador de Pedidos",
    description="Servicio encargado de la coordinación y gestión de pedidos de venta, con validación de clientes e inventario. \n\n" \
    "Este servicio actúa como el punto central de integración entre los departamentos de Clientes, Productos e Inventario para garantizar la correcta ejecución de las ventas. \n\n" \
    "Ejecutar en puerto **8002** y asegurarse de que los servicios de Clientes (8000), Productos (8001) e Inventario (8003) estén activos para su correcto funcionamiento.",
    version="2.0.0",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

FILE_NAME = "pedidos.csv"
HEADERS = ["id_pedido", "id_cliente", "id_producto", "cantidad"]

if not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

class Pedido(BaseModel):
    id_pedido: int = Field(..., example=501)  # type: ignore
    id_cliente: int = Field(..., example=101) # type: ignore
    id_producto: int = Field(..., example=1) # type: ignore
    cantidad: int = Field(..., gt=0, example=2) # type: ignore

class PedidoRegistro(BaseModel):
    id_cliente: int = Field(..., example=101) # type: ignore
    id_producto: int = Field(..., example=1) # type: ignore
    cantidad: int = Field(..., gt=0, example=2) # type: ignore

# URLs de los servicios (Ventanillas externas)
URL_CLIENTES = "http://127.0.0.1:8000/clientes"
URL_PRODUCTOS = "http://127.0.0.1:8001/productos"
URL_INVENTARIO = "http://127.0.0.1:8003/inventario"

def leer_pedidos():
    """Lee todos los pedidos del archivo CSV."""
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

@app.get(
    "/pedidos",
    response_model=List[Pedido],
    tags=["Consultas"],
    summary="Obtener lista de pedidos",
    status_code=200,
    responses={
        200: {
            "description": "Lista de pedidos obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id_pedido": 501,
                            "id_cliente": 101,
                            "id_producto": 1,
                            "cantidad": 2
                        }
                    ]
                }
            }
        }
    }
)
def obtener_pedidos():
    """Retorna el registro oficial de pedidos desde el archivo CSV.
    
    Este endpoint obtiene la lista completa de todos los pedidos registrados
    en la base de datos de pedidos persistente (archivo CSV).
    
    Returns:
        List[Pedido]: Lista de pedidos con todos sus datos.
    """
    return leer_pedidos()

@app.post(
    "/pedidos",
    tags=["Operaciones"],
    summary="Crear nuevo pedido",
    status_code=201,
    responses={
        201: {
            "description": "Pedido creado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Venta completada y stock descontado",
                        "id_pedido": 501,
                        "status": "success"
                    }
                }
            }
        },
        400: {
            "description": "Datos inválidos: cliente no existe, producto no existe, inventario insuficiente"
        },
        503: {
            "description": "Servicios de catálogo o inventario no disponibles"
        }
    }
)
def crear_pedido(p: PedidoRegistro):
    """Crea un nuevo pedido con validación integrada de clientes e inventario.
    
    Ejecuta el siguiente flujo de validación:
    1. Consulta el servicio de productos para verificar que el producto existe
    2. Verifica que hay inventario suficiente para completar el pedido
    3. Valida que el cliente existe en el padrón oficial
    4. Si todo es válido: descuenta el inventario y persiste el pedido
    
    Args:
        p (PedidoRegistro): Datos del pedido a crear.
            - id_cliente: ID del cliente que realiza el pedido
            - id_producto: ID del producto a ordenar
            - cantidad: Cantidad de unidades a ordenar (debe ser mayor a 0)
    
    Returns:
        dict: Diccionario con mensaje de éxito e ID asignado del pedido.
    
    Raises:
        HTTPException: Con status 400 si hay problemas de validación.
        HTTPException: Con status 503 si no hay disponibilidad de servicios.
    """
    # PASO 1: Consultar Productos e Inventario
    try:
        # a) ¿Existe el producto?
        res_p = requests.get(URL_PRODUCTOS)
        if not any(int(prod['id_producto']) == p.id_producto for prod in res_p.json()):
            raise HTTPException(status_code=400, detail="Producto no existe en el catálogo")
        
        # b) ¿Hay inventario suficiente?
        res_i = requests.get(f"{URL_INVENTARIO}/{p.id_producto}")
        if res_i.status_code == 404:
            raise HTTPException(status_code=400, detail="Producto sin registro de inventario")
        
        stock_actual = res_i.json()['cantidad']
        # Validación: mayor que 0 y suficiente para lo pedido
        if stock_actual <= 0 or p.cantidad > stock_actual:
            raise HTTPException(status_code=400, detail="Inventario insuficiente para completar el pedido")

    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Servicios de catálogo o inventario no disponibles")

    # PASO 2: Consultar Cliente y completar
    try:
        res_c = requests.get(URL_CLIENTES)
        if not any(int(c['id_cliente']) == p.id_cliente for c in res_c.json()):
            raise HTTPException(status_code=400, detail="El cliente no existe en el padrón oficial")
        
        # PASO 3: Si TODO es CORRECTO: Descontar inventario y Persistir pedido
        requests.post(f"{URL_INVENTARIO}/descontar", json={"id_producto": p.id_producto, "cantidad": p.cantidad})
        
        # Generar ID autoincremental para el pedido
        pedidos = leer_pedidos()
        if pedidos:
            siguiente_id = max(int(ped['id_pedido']) for ped in pedidos) + 1
        else:
            siguiente_id = 1
        
        # Guardar pedido en pedidos.csv
        with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([siguiente_id, p.id_cliente, p.id_producto, p.cantidad])
        
        return {"mensaje": "Venta completada y stock descontado", "id_pedido": siguiente_id, "status": "success"}

    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Departamento de Clientes no disponible")