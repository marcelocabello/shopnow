---
name: shopnow-project
description: "ShopNow microservices project. Use when: setting up development environment, running services, deploying with Docker, understanding the architecture, or configuring RabbitMQ."
---

# ShopNow Microservices Project

## Project Overview

ShopNow is a microservices-based e-commerce system with four independent services communicating through RabbitMQ message bus:

- **Clientes** (Port 8010): Customer management
- **Productos** (Port 8001): Product catalog
- **Pedidos** (Port 8002): Order processing
- **Inventario** (Port 8003): Inventory management

### Architecture

```
┌─────────────────────────────────────────────────────┐
│              RabbitMQ Bus (Port 5672)               │
│         Exchange: 'servicios' (type: direct)        │
└─────────────────────────────────────────────────────┘
         △  △  △  △
         │  │  │  │
    ┌────┘  │  │  └────┐
    │       │  │       │
    ▼       ▼  ▼       ▼
┌────────┐ ┌───────┐ ┌──────┐ ┌────────┐
│Pedidos │ │Prod.  │ │Client│ │Inv.   │
│ :8002  │ │ :8001 │ │:8000 │ │:8003  │
└────────┘ └───────┘ └──────┘ └────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- Docker & Docker Compose (for full setup)
- Virtual environment activated

### Option 1: Quick Run with Docker Compose (Recommended)

```bash
# Start RabbitMQ and verify it's healthy
docker-compose up -d

# In a new terminal, activate venv and run all services
source .venv/bin/activate
bash shopnow.sh start
```

Access services at:
- Clientes Swagger: http://localhost:8000/docs
- Productos Swagger: http://localhost:8001/docs
- Pedidos Swagger: http://localhost:8002/docs
- Inventario Swagger: http://localhost:8003/docs
- RabbitMQ Dashboard: http://localhost:15672 (guest/guest)

### Option 2: Manual Service Setup (Per Terminal)

**Terminal 1 - RabbitMQ**
```bash
docker-compose up -d
```

**Terminal 2 - Clientes**
```bash
source .venv/bin/activate
uvicorn serv_clientes:app --port 8000 --reload
```

**Terminal 3 - Productos**
```bash
source .venv/bin/activate
uvicorn serv_productos:app --port 8001 --reload
```

**Terminal 4 - Pedidos**
```bash
source .venv/bin/activate
uvicorn serv_pedidos:app --port 8002 --reload
```

**Terminal 5 - Inventario**
```bash
source .venv/bin/activate
uvicorn serv_inventario:app --port 8003 --reload
```

---

## Service Management

### Using shopnow.sh Script

```bash
# Start all services
bash shopnow.sh start

# Stop all services
bash shopnow.sh stop

# Show status
bash shopnow.sh status

# Show help
bash shopnow.sh
```

### Stop Everything

```bash
# Stop services
bash shopnow.sh stop

# Stop RabbitMQ container
docker-compose down
```

---

## Environment Setup

### First Time Setup

```bash
# Navigate to project
cd /home/boomer/ITQ/SOA/ShopNow

# Create virtual environment (if not exists)
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install fastapi uvicorn pika pydantic[email]
```

### Dependencies

- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **pika**: RabbitMQ client
- **pydantic**: Data validation

---

## Data Files

The project includes CSV-based data storage:

- `clientes.csv`: Customer data
- `productos.csv`: Product catalog
- `pedidos.csv`: Order records
- `inventario.csv`: Inventory levels

> These are persistent across service restarts

---

## Development Guidelines

### Message Queue Pattern

Services communicating via RabbitMQ:
- **serv_pedidos** sends requests and waits for responses on queues
- Other services listen on their respective queues and respond
- Uses direct exchange routing by service name

### Adding New Endpoints

1. Add route in appropriate service file
2. Update message handlers if it requires inter-service communication
3. Publish changes (services auto-reload with `--reload` flag)

### Debugging

1. Access service Swagger docs at `http://localhost:<port>/docs`
2. Check RabbitMQ dashboard: http://localhost:15672
3. Monitor logs in each terminal window
4. Use `rabbitmq_client.py` for manual queue testing

---

## Common Tasks

### Test a Service

```bash
curl http://localhost:8000/docs  # Clientes
curl http://localhost:8001/docs  # Productos
curl http://localhost:8002/docs  # Pedidos
curl http://localhost:8003/docs  # Inventario
```

### View RabbitMQ Stats

Open http://localhost:15672 → Login (guest/guest) → Queues tab

### Reset Data

Delete the CSV files and restart services:
```bash
rm *.csv
bash shopnow.sh stop && bash shopnow.sh start
```

---

## Troubleshooting

**RabbitMQ won't connect:**
- Verify RabbitMQ container is running: `docker ps | grep rabbitmq`
- Restart: `docker-compose restart rabbitmq`

**Service won't start:**
- Check port not in use: `lsof -i :8000` (replace with port)
- Verify venv activated: `which python` should show `.venv/bin`

**Port already in use:**
```bash
# Kill process on specific port
lsof -ti :8000 | xargs kill -9
```

---

## Documentation

- [RabbitMQ Deployment Guide](./RABBITMQ_DEPLOYMENT.md): Detailed messaging architecture
- Individual service files: `serv_*.py`
