#!/bin/bash

# Script para gestionar servicios de ShopNow
# Uso: ./shopnow.sh [start|stop|status]

# Función para mostrar ayuda
mostrar_ayuda() {
    echo "Uso: ./shopnow.sh [start|stop|status]"
    echo ""
    echo "Opciones:"
    echo "  start   - Levanta todos los servicios de ShopNow"
    echo "  stop    - Detiene todos los servicios de ShopNow"
    echo "  status  - Muestra el estado de los servicios"
    echo ""
    echo "Servicios:"
    echo "  Clientes:   puerto 8000"
    echo "  Productos:  puerto 8001"
    echo "  Pedidos:    puerto 8002"
    echo "  Inventario: puerto 8003"
}

# Función para levantar servicios
iniciar_servicios() {
    echo "========================================"
    echo "Levantando servicios de ShopNow..."
    echo "========================================"
    echo ""
    echo "Clientes: Puerto 8000"
    uvicorn serv_clientes:app --port 8000 --reload > /dev/null 2>&1 &
    CLIENTE_PID=$!
    echo "  PID: $CLIENTE_PID"
    echo ""
    
    echo "Productos: Puerto 8001"
    uvicorn serv_productos:app --port 8001 --reload > /dev/null 2>&1 &
    PRODUCTO_PID=$!
    echo "  PID: $PRODUCTO_PID"
    echo ""
    
    echo "Pedidos: Puerto 8002"
    uvicorn serv_pedidos:app --port 8002 --reload > /dev/null 2>&1 &
    PEDIDO_PID=$!
    echo "  PID: $PEDIDO_PID"
    echo ""
    
    echo "Inventario: Puerto 8003"
    uvicorn serv_inventario:app --port 8003 --reload > /dev/null 2>&1 &
    INVENTARIO_PID=$!
    echo "  PID: $INVENTARIO_PID"
    echo ""
    
    echo "========================================"
    echo "✓ Servicios levantados exitosamente"
    echo "========================================"
    echo ""
    echo "Acceso a documentación Swagger:"
    echo "  • Clientes:   http://localhost:8000/docs"
    echo "  • Productos:  http://localhost:8001/docs"
    echo "  • Pedidos:    http://localhost:8002/docs"
    echo "  • Inventario: http://localhost:8003/docs"
}

# Función para detener servicios
detener_servicios() {
    echo "========================================"
    echo "Deteniendo servicios de ShopNow..."
    echo "========================================"
    echo ""
    
    # Matar procesos de uvicorn
    pkill -f "uvicorn serv_clientes:app"
    if [ $? -eq 0 ]; then
        echo "✓ Clientes (puerto 8000) - Detenido"
    else
        echo "✗ Clientes (puerto 8000) - No estaba ejecutándose"
    fi
    
    pkill -f "uvicorn serv_productos:app"
    if [ $? -eq 0 ]; then
        echo "✓ Productos (puerto 8001) - Detenido"
    else
        echo "✗ Productos (puerto 8001) - No estaba ejecutándose"
    fi
    
    pkill -f "uvicorn serv_pedidos:app"
    if [ $? -eq 0 ]; then
        echo "✓ Pedidos (puerto 8002) - Detenido"
    else
        echo "✗ Pedidos (puerto 8002) - No estaba ejecutándose"
    fi
    
    pkill -f "uvicorn serv_inventario:app"
    if [ $? -eq 0 ]; then
        echo "✓ Inventario (puerto 8003) - Detenido"
    else
        echo "✗ Inventario (puerto 8003) - No estaba ejecutándose"
    fi
    
    echo ""
    echo "========================================"
    echo "✓ Todos los servicios han sido detenidos"
    echo "========================================"
}

# Función para ver estado de servicios
verificar_estado() {
    echo "========================================"
    echo "Estado de servicios de ShopNow"
    echo "========================================"
    echo ""
    
    # Verificar cada puerto
    pgrep -f "uvicorn serv_clientes:app" > /dev/null
    if [ $? -eq 0 ]; then
        PID=$(pgrep -f "uvicorn serv_clientes:app")
        echo "✓ Clientes (puerto 8000) - EJECUTÁNDOSE (PID: $PID)"
    else
        echo "✗ Clientes (puerto 8000) - DETENIDO"
    fi
    
    pgrep -f "uvicorn serv_productos:app" > /dev/null
    if [ $? -eq 0 ]; then
        PID=$(pgrep -f "uvicorn serv_productos:app")
        echo "✓ Productos (puerto 8001) - EJECUTÁNDOSE (PID: $PID)"
    else
        echo "✗ Productos (puerto 8001) - DETENIDO"
    fi
    
    pgrep -f "uvicorn serv_pedidos:app" > /dev/null
    if [ $? -eq 0 ]; then
        PID=$(pgrep -f "uvicorn serv_pedidos:app")
        echo "✓ Pedidos (puerto 8002) - EJECUTÁNDOSE (PID: $PID)"
    else
        echo "✗ Pedidos (puerto 8002) - DETENIDO"
    fi
    
    pgrep -f "uvicorn serv_inventario:app" > /dev/null
    if [ $? -eq 0 ]; then
        PID=$(pgrep -f "uvicorn serv_inventario:app")
        echo "✓ Inventario (puerto 8003) - EJECUTÁNDOSE (PID: $PID)"
    else
        echo "✗ Inventario (puerto 8003) - DETENIDO"
    fi
    
    echo ""
    echo "========================================"
}

# Script principal
if [ $# -eq 0 ]; then
    mostrar_ayuda
    exit 0
fi

case "$1" in
    start)
        iniciar_servicios
        ;;
    stop)
        detener_servicios
        ;;
    status)
        verificar_estado
        ;;
    *)
        echo "Error: Opción no reconocida: $1"
        echo ""
        mostrar_ayuda
        exit 1
        ;;
esac