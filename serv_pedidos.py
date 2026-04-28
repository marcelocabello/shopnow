import csv
import os
import json
import pika
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import List
from rabbitmq_client import ROUTING_KEYS, create_rabbitmq_client
from auth import verificar_token, endpoint_login, Token


@asynccontextmanager
async def lifespan(app):
    """Maneja el startup y shutdown de la aplicación con RabbitMQ"""
    try:
        print("▶ Conectando a RabbitMQ...")
        mq_client.connect()
        # Declarar el exchange
        mq_client.declare_exchange('servicios', exchange_type='direct')
        # Declarar y vincular cola para pedidos asíncronos
        mq_client.declare_queue('pedidos_requests')
        mq_client.bind_queue('pedidos_requests', 'servicios', ROUTING_KEYS['crear_pedido'])
        # Iniciar consumidor de pedidos encolados
        mq_client.start_consumer_thread('pedidos_requests', handle_pedido_message)
        print("✓ Servicio de Pedidos iniciado y conectado a RabbitMQ (consumer activo)")
    except Exception as e:
        print(f"⚠ Advertencia: Error al conectar a RabbitMQ en startup: {e}")
        print("ℹ El servicio seguirá ejecutándose pero sin soporte de mensajería RabbitMQ")
    
    yield
    
    try:
        mq_client.close()
        print("✓ Servicio de Pedidos desconectado de RabbitMQ")
    except Exception as e:
        print(f"Error al desconectar de RabbitMQ: {e}")


app = FastAPI(
    lifespan=lifespan,
    title="Coordinador de Pedidos",
    description="Servicio encargado de la coordinación y gestión de pedidos de venta, con validación de clientes e inventario. \n\n" \
    "Este servicio actúa como el punto central de integración entre los departamentos de Clientes, Productos e Inventario para garantizar la correcta ejecución de las ventas. \n\n" \
    "Ejecutar en puerto **8002** y asegurarse de que los servicios de Clientes (8010), Productos (8001) e Inventario (8003) estén activos para su correcto funcionamiento. \n\n" \
    "**Versión RabbitMQ**: Ahora se comunica a través de un bus de mensajería.",
    version="3.0.0 - RabbitMQ",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

FILE_NAME = "pedidos.csv"
HEADERS = ["id_pedido", "id_cliente", "id_producto", "cantidad"]

if not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

# Cliente RabbitMQ global
mq_client = create_rabbitmq_client()

class Pedido(BaseModel):
    id_pedido: int = Field(..., example=501)  # type: ignore
    id_cliente: int = Field(..., example=101) # type: ignore
    id_producto: int = Field(..., example=1) # type: ignore
    cantidad: int = Field(..., gt=0, example=2) # type: ignore

class PedidoRegistro(BaseModel):
    id_cliente: int = Field(..., example=101) # type: ignore
    id_producto: int = Field(..., example=1) # type: ignore
    cantidad: int = Field(..., gt=0, example=2) # type: ignore

def leer_pedidos():
    """Lee todos los pedidos del archivo CSV."""
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ============================================================================
# CONSUMIDOR ASYNC DE PEDIDOS (maneja mensajes encolados vía RabbitMQ)
# ============================================================================

def _procesar_pedido_data(id_cliente: int, id_producto: int, cantidad: int):
    """Lógica de negocio compartida entre endpoint síncrono y consumidor async.
    
    Returns: dict con id_pedido generado
    Raises: HTTPException si falla validación de negocio (no reencolar)
    Raises: RuntimeError si hay timeout de servicio (sí reencolar)
    """
    # Validar producto
    resp = mq_client.request_reply(
        exchange='servicios',
        routing_key=ROUTING_KEYS['validate_producto'],
        message={'id_producto': id_producto}
    )
    if resp is None:
        raise RuntimeError("Timeout servicio productos")
    if not resp.get('existe'):
        raise HTTPException(status_code=400, detail="Producto no existe en el catálogo")

    # Verificar inventario
    resp = mq_client.request_reply(
        exchange='servicios',
        routing_key=ROUTING_KEYS['get_inventario'],
        message={'id_producto': id_producto}
    )
    if resp is None:
        raise RuntimeError("Timeout servicio inventario")
    stock = resp.get('cantidad', 0)
    if stock <= 0:
        raise HTTPException(status_code=400, detail="Producto sin registro de inventario")
    if cantidad > stock:
        raise HTTPException(status_code=400, detail="Inventario insuficiente para completar el pedido")

    # Validar cliente
    resp = mq_client.request_reply(
        exchange='servicios',
        routing_key=ROUTING_KEYS['validate_cliente'],
        message={'id_cliente': id_cliente}
    )
    if resp is None:
        raise RuntimeError("Timeout servicio clientes")
    if not resp.get('existe'):
        raise HTTPException(status_code=400, detail="El cliente no existe en el padrón oficial")

    # Descontar inventario
    resp = mq_client.request_reply(
        exchange='servicios',
        routing_key=ROUTING_KEYS['descontar_inventario'],
        message={'id_producto': id_producto, 'cantidad': cantidad}
    )
    if resp is None:
        raise RuntimeError("Timeout al descontar inventario")
    if not resp.get('exito'):
        raise HTTPException(status_code=503, detail="Error al descontar inventario")

    # Persistir pedido
    pedidos = leer_pedidos()
    siguiente_id = max((int(p['id_pedido']) for p in pedidos), default=500) + 1
    with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([siguiente_id, id_cliente, id_producto, cantidad])

    return siguiente_id


def handle_pedido_message(ch, method, properties, body):
    """Consumidor RabbitMQ para pedidos encolados.
    
    - Si hay timeout (servicio caído): NACK + requeue=True (el mensaje regresa a la cola)
    - Si falla validación de negocio: NACK + requeue=False (rechazo permanente)
    - Si éxito: ACK y el pedido queda guardado
    """
    try:
        message = json.loads(body)
        print(f"📨 Procesando pedido encolado: {message}")
        id_cliente = message['id_cliente']
        id_producto = message['id_producto']
        cantidad = message['cantidad']

        id_pedido = _procesar_pedido_data(id_cliente, id_producto, cantidad)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"✓ Pedido {id_pedido} procesado y guardado desde cola")

    except RuntimeError as e:
        # Timeout - servicio caído, reencolar para reintento
        print(f"⚠ Timeout al procesar pedido encolado ({e}). Reencolándolo...")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except HTTPException as e:
        # Error de negocio - rechazar definitivamente
        print(f"✗ Pedido inválido, rechazando (sin requeue): {e.detail}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        print(f"✗ Error inesperado procesando pedido: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def _publicar_pedido_encolado(p: PedidoRegistro):
    """Publica un pedido en RabbitMQ para procesamiento asíncrono."""
    mq_client.publish(
        exchange='servicios',
        routing_key=ROUTING_KEYS['crear_pedido'],
        message={
            "id_cliente": p.id_cliente,
            "id_producto": p.id_producto,
            "cantidad": p.cantidad,
        },
    )


# ============================================================================
# AUTENTICACIÓN
# ============================================================================

@app.post("/token", response_model=Token, tags=["Autenticación"], summary="Obtener token JWT")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Genera un JWT Bearer token. Usuarios: admin/admin123, usuario/pass123."""
    return endpoint_login(form_data)

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
def obtener_pedidos(usuario: str = Depends(verificar_token)):
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
    summary="Crear nuevo pedido (asíncrono por defecto)",
    status_code=202,
    responses={
        202: {
            "description": "Pedido encolado exitosamente. Se procesará automáticamente cuando todos los servicios estén disponibles.",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Pedido encolado exitosamente",
                        "status": "queued"
                    }
                }
            }
        },
        503: {
            "description": "No se pudo conectar a RabbitMQ"
        }
    }
)
def crear_pedido(p: PedidoRegistro, usuario: str = Depends(verificar_token)):
    """Encola un pedido para procesamiento asíncrono.

    El consumidor de RabbitMQ aplica validaciones de negocio y, si hay timeout
    por servicios caídos, re-encola automáticamente hasta poder procesarlo.
    """
    try:
        _publicar_pedido_encolado(p)
        return {
            "mensaje": "Pedido encolado exitosamente",
            "status": "queued",
            "nota": "Se procesará cuando todos los servicios estén disponibles",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"No se pudo encolar el pedido: {e}")


# Las funciones de startup y shutdown ahora están en el contexto lifespan
