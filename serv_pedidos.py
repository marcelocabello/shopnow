import csv
import os
import json
import pika
from urllib import request, parse, error
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
    """Startup/shutdown de Pedidos con Postgres + consumidor RabbitMQ."""
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
    try:
        mq_client.connect()
        mq_client.declare_exchange("servicios", "direct")
        mq_client.declare_queue("pedidos_requests")
        mq_client.bind_queue("pedidos_requests", "servicios", ROUTING_KEYS["crear_pedido"])
        mq_client.start_consumer_thread("pedidos_requests", handle_pedido_message)
        print("✓ Consumidor RabbitMQ de Pedidos activo")
    except Exception as exc:
        print(f"⚠ Pedidos sin consumidor RabbitMQ: {exc}")
    yield
    try:
        mq_client.close()
    except Exception:
        pass


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
CLIENTES_URL = os.getenv("CLIENTES_URL", "http://127.0.0.1:8010").rstrip("/")
PRODUCTOS_URL = os.getenv("PRODUCTOS_URL", "http://127.0.0.1:8001").rstrip("/")
INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://127.0.0.1:8003").rstrip("/")
SERVICE_USER = os.getenv("SERVICE_AUTH_USER", "admin")
SERVICE_PASSWORD = os.getenv("SERVICE_AUTH_PASSWORD", "admin123")

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
    """Lógica de negocio para consumidor async.
    
    Returns: dict con id_pedido generado
    Raises: HTTPException si falla validación de negocio (no reencolar)
    Raises: RuntimeError si hay timeout de servicio (sí reencolar)
    """
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


def _http_json(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None):
    data = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = request.Request(url=url, data=data, method=method, headers=req_headers)
    with request.urlopen(req, timeout=12) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _service_token(base_url: str) -> str:
    form = parse.urlencode(
        {
            "username": SERVICE_USER,
            "password": SERVICE_PASSWORD,
            "grant_type": "password",
        }
    ).encode("utf-8")
    req = request.Request(
        url=f"{base_url}/token",
        data=form,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    with request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        token = data.get("access_token")
        if not token:
            raise HTTPException(status_code=503, detail=f"Token inválido de servicio en {base_url}")
        return token


def _auth_headers(base_url: str) -> dict:
    return {"Authorization": f"Bearer {_service_token(base_url)}"}


def _validar_dependencias_rest(id_cliente: int, id_producto: int, cantidad: int):
    try:
        token_clientes = _auth_headers(CLIENTES_URL)
        token_productos = _auth_headers(PRODUCTOS_URL)
        token_inventario = _auth_headers(INVENTARIO_URL)

        _http_json(f"{CLIENTES_URL}/clientes/{id_cliente}", headers=token_clientes)
        _http_json(f"{PRODUCTOS_URL}/productos/{id_producto}", headers=token_productos)
        stock_info = _http_json(f"{INVENTARIO_URL}/inventario/{id_producto}", headers=token_inventario)
    except error.HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=400, detail="Validación fallida: cliente/producto/inventario no encontrado") from exc
        if exc.code in (401, 403):
            raise HTTPException(status_code=503, detail="Error de autenticación entre servicios") from exc
        if exc.code == 503:
            raise HTTPException(status_code=503, detail="Un departamento está temporalmente no disponible") from exc
        raise HTTPException(status_code=503, detail=f"Error HTTP de dependencia: {exc.code}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo validar dependencias REST: {exc}") from exc

    stock = int(stock_info.get("cantidad", 0))
    if stock <= 0 or cantidad > stock:
        raise HTTPException(status_code=400, detail="Inventario insuficiente para completar el pedido")


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
    status_code=202,
    responses={
        202: {
            "description": "Pedido encolado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Pedido encolado exitosamente",
                        "status": "queued",
                        "nota": "Se procesará en segundo plano vía RabbitMQ"
                    }
                }
            }
        }
    }
)
def crear_pedido(p: PedidoRegistro, usuario: str = Depends(verificar_token)):
    """Orquesta validaciones REST y encola pedido para procesamiento async."""
    if STARTUP_ERROR:
        raise HTTPException(
            status_code=503,
            detail=f"Servicio temporalmente no disponible: {STARTUP_ERROR}",
        )
    _validar_dependencias_rest(p.id_cliente, p.id_producto, p.cantidad)
    try:
        _publicar_pedido_encolado(p)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo encolar el pedido: {exc}") from exc
    return {
        "mensaje": "Pedido encolado exitosamente",
        "status": "queued",
        "nota": "Se procesará en segundo plano vía RabbitMQ",
    }


# Las funciones de startup y shutdown ahora están en el contexto lifespan
