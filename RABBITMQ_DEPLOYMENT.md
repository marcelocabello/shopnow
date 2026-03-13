# ShopNow RabbitMQ Deployment Guide

## Version 3.0 - RabbitMQ Messaging Architecture

This guide explains how to run the ShopNow microservices with RabbitMQ messaging instead of direct HTTP calls.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    RabbitMQ Bus                         │
│  (exchange: 'servicios', type: 'direct')                │
└─────────────────────────────────────────────────────────┘
         ▲  ▲  ▲  ▲
         │  │  │  │
    ┌────┘  │  │  └────┐
    │       │  │       │
    ▼       ▼  ▼       ▼
┌────────┐ ┌───────────┐ ┌────────────┐ ┌───────────┐
│Pedidos │ │ Productos │ │  Clientes  │ │Inventario │
│ :8002  │ │   :8001   │ │   :8000    │ │  :8003    │
└────────┘ └───────────┘ └────────────┘ └───────────┘
```

**Communication Pattern**: serv_pedidos sends requests via RabbitMQ and waits for responses from other services listening on their queues.

---

## Quick Start (Local Setup)

### Prerequisites
- Python 3.9+
- RabbitMQ running on `localhost:5672`
- FastAPI and pika installed

### 1. Start RabbitMQ

**Option A: Using Docker**
```bash
docker run -d --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  rabbitmq:3-management
```

Then access the RabbitMQ dashboard at http://localhost:15672 (default user: guest/guest)

**Option B: Using the provided docker-compose**
```bash
docker-compose up -d rabbitmq
```

### 2. Install Python Dependencies
```bash
source .venv/bin/activate
pip install fastapi uvicorn pika pydantic[email]
```

### 3. Run Services

Open separate terminals for each service:

**Terminal 1 - Clientes (Port 8000)**
```bash
source .venv/bin/activate
uvicorn serv_clientes:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Productos (Port 8001)**
```bash
source .venv/bin/activate
uvicorn serv_productos:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 3 - Pedidos (Port 8002)**
```bash
source .venv/bin/activate
uvicorn serv_pedidos:app --host 0.0.0.0 --port 8002 --reload
```

**Terminal 4 - Inventario (Port 8003)**
```bash
source .venv/bin/activate
uvicorn serv_inventario:app --host 0.0.0.0 --port 8003 --reload
```

### 4. Verify Services are Running

Check that all services are connected to RabbitMQ:

```bash
# You should see messages like:
# ✓ Conectado a RabbitMQ en localhost:5672
# ✓ Servicio de Clientes iniciado y escuchando en RabbitMQ
# ✓ Servicio de Productos iniciado y escuchando en RabbitMQ
# ✓ Servicio de Pedidos iniciado y conectado a RabbitMQ
# ✓ Servicio de Inventario iniciado y escuchando en RabbitMQ
```

---

## Docker Deployment

### Full Stack with Docker Compose

```bash
docker-compose up
```

This starts:
- RabbitMQ (port 5672, dashboard at 15672)
- All four microservices

**Note**: Services are configured to connect to `localhost` by default. For Docker container-to-container communication, update `rabbitmq_client.py`:

```python
# Change from:
mq_client = RabbitMQClient(host='localhost', port=5672)

# To:
mq_client = RabbitMQClient(host='rabbitmq', port=5672)
```

---

## Message Flow

### Creating a New Order (Pedido)

```
POST /pedidos → serv_pedidos
  ├─ Send RabbitMQ request: "validate_producto"
  │   └─→ serv_productos listens and responds
  ├─ Send RabbitMQ request: "get_inventario"  
  │   └─→ serv_inventario listens and responds
  ├─ Send RabbitMQ request: "validate_cliente"
  │   └─→ serv_clientes listens and responds
  ├─ Send RabbitMQ request: "descontar_inventario"
  │   └─→ serv_inventario deducts stock
  └─ Save order to CSV → Returns success
```

### Queue Configuration

| Queue | Routing Key | Handler |
|-------|------------|---------|
| `productos_requests` | `productos.validate` | serv_productos - validates if product exists |
| `clientes_requests` | `clientes.validate` | serv_clientes - validates if client exists |
| `inventario_requests` | `inventario.get` | serv_inventario - returns current stock |
| `inventario_requests` | `inventario.descontar` | serv_inventario - deducts stock |

---

## API Endpoints (Unchanged)

All original FastAPI endpoints remain the same:

- `GET /clientes` - List all clients
- `POST /clientes` - Register new client
- `GET /productos` - List all products
- `POST /productos` - Register new product
- `GET /pedidos` - List all orders
- `POST /pedidos` - Create new order (via RabbitMQ)
- `GET /inventario` - List all inventory
- `GET /inventario/{id_producto}` - Get product stock

---

## Debugging

### View RabbitMQ Queue Status

Access the RabbitMQ Management Console:
- URL: http://localhost:15672
- Username: guest
- Password: guest

### Check Service Logs

Each service prints RabbitMQ connection status:

```
✓ Conectado a RabbitMQ en localhost:5672
📨 Mensaje recibido en Clientes: {'id_cliente': 101}
✓ Respuesta enviada: {'existe': True}
```

### Test Connection

Run this from Python to test RabbitMQ connectivity:

```python
from rabbitmq_client import RabbitMQClient

client = RabbitMQClient(host='localhost', port=5672)
client.connect()
print("✓ Connected successfully!")
client.close()
```

---

## Environment Variables (Optional)

You can set these to customize RabbitMQ host:

```bash
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
```

Then update services to use:
```python
import os
host = os.getenv('RABBITMQ_HOST', 'localhost')
port = int(os.getenv('RABBITMQ_PORT', 5672))
mq_client = RabbitMQClient(host=host, port=port)
```

---

## Transitioning from HTTP to RabbitMQ

**What changed**: 
- Internal service-to-service communication now uses RabbitMQ instead of HTTP
- External API endpoints remain accessible via HTTP (unchanged)
- Request-reply pattern ensures synchronous responses

**What stayed the same**:
- CSV file storage for persistence
- FastAPI interface
- Port assignments
- Data models and validation

---

## Troubleshooting

### Connection Refused
```
✗ Error conectando a RabbitMQ: [Errno 111] Connection refused
```
**Solution**: Make sure RabbitMQ is running and accessible on the configured host/port.

### Timeout Waiting for Response
```
⏱ Timeout esperando respuesta con correlation_id: ...
```
**Solution**: Check if the target service is running and connected to RabbitMQ.

### Service Won't Start
**Check**:
1. Are all Python dependencies installed? (`pip install pika`)
2. Is RabbitMQ accessible?
3. Are there port conflicts with other services?

---

## Next Steps

- Monitor queue performance using the RabbitMQ dashboard
- Implement dead letter queues for failed messages
- Add message encryption for production
- Scale services horizontally with load balancing
