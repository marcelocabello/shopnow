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
import storage
from ui_pages import render_service_ui


STARTUP_ERROR: str | None = None


@asynccontextmanager
async def lifespan(app):
    """Startup/shutdown sin dependencia de RabbitMQ."""
    global STARTUP_ERROR
    if storage.postgres_enabled():
        try:
            storage.ensure_schema()
            storage.seed_demo_data_if_enabled()
            STARTUP_ERROR = None
            print("✓ Postgres habilitado para servicio de Pedidos")
        except Exception as exc:
            STARTUP_ERROR = str(exc)
            print(f"⚠ Pedidos inició en modo degradado: {STARTUP_ERROR}")
    yield


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


@app.get("/ui", include_in_schema=False)
def pedidos_ui():
    return render_service_ui("pedidos", "ShopNow Pedidos")


@app.get("/", include_in_schema=False)
def pedidos_home():
    return {"servicio": "pedidos", "ui": "/ui", "docs": "/docs"}


FILE_NAME = "pedidos.csv"
HEADERS = ["id_pedido", "id_cliente", "id_producto", "cantidad"]

if not storage.postgres_enabled() and not os.path.exists(FILE_NAME):
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
    if STARTUP_ERROR:
        raise HTTPException(
            status_code=503,
            detail=f"Servicio temporalmente no disponible: {STARTUP_ERROR}",
        )
    if storage.postgres_enabled():
        return storage.read_pedidos()
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
    if storage.postgres_enabled():
        return storage.create_pedido(id_cliente, id_producto, cantidad)

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
    summary="Crear nuevo pedido",
    status_code=201,
    responses={
        201: {
            "description": "Pedido creado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Pedido creado exitosamente",
                        "id_pedido": 501,
                        "status": "success"
                    }
                }
            }
        }
    }
)
def crear_pedido(p: PedidoRegistro, usuario: str = Depends(verificar_token)):
    """Crea un pedido de forma síncrona (sin RabbitMQ)."""
    if STARTUP_ERROR:
        raise HTTPException(
            status_code=503,
            detail=f"Servicio temporalmente no disponible: {STARTUP_ERROR}",
        )
    if storage.postgres_enabled():
        id_pedido = storage.create_pedido(p.id_cliente, p.id_producto, p.cantidad)
    else:
        pedidos = leer_pedidos()
        id_pedido = max((int(item["id_pedido"]) for item in pedidos), default=500) + 1
        with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([id_pedido, p.id_cliente, p.id_producto, p.cantidad])
    return {"mensaje": "Pedido creado exitosamente", "id_pedido": id_pedido, "status": "success"}


# Las funciones de startup y shutdown ahora están en el contexto lifespan
