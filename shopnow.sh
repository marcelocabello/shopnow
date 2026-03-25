#!/bin/bash

# Script para gestionar servicios de ShopNow
# Uso: ./shopnow.sh [start|stop|status]

# ============================================================================
# DEFINICIÓN DE COLORES
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m'  # No Color

# ============================================================================
# FUNCIÓN: Mostrar ayuda
# ============================================================================
mostrar_ayuda() {
    echo -e "${CYAN}Uso: ./shopnow.sh [start|stop|status]${NC}"
    echo ""
    echo -e "${WHITE}Opciones:${NC}"
    echo -e "  ${GREEN}start${NC}   - Levanta RabbitMQ y todos los servicios de ShopNow"
    echo -e "  ${RED}stop${NC}    - Detiene todos los servicios y RabbitMQ"
    echo -e "  ${BLUE}status${NC}  - Muestra el estado de los servicios"
    echo ""
    echo -e "${WHITE}Servicios:${NC}"
    echo -e "  ${MAGENTA}RabbitMQ${NC}:  puerto 5672 (amqp), 15672 (dashboard)"
    echo -e "  ${MAGENTA}Clientes${NC}:   puerto 8000"
    echo -e "  ${MAGENTA}Productos${NC}:  puerto 8001"
    echo -e "  ${MAGENTA}Pedidos${NC}:    puerto 8002"
    echo -e "  ${MAGENTA}Inventario${NC}: puerto 8003"
}

# ============================================================================
# FUNCIÓN: Levantar servicios
# ============================================================================
iniciar_servicios() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}       INICIANDO SHOPNOW - RabbitMQ + Microservicios${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Verificar que existe docker-compose.yml
    if [ ! -f "docker-compose.yml" ]; then
        echo -e "${RED}✗ Error: docker-compose.yml no encontrado${NC}"
        return 1
    fi
    
    # Iniciar RabbitMQ
    echo -e "${YELLOW}▶ Iniciando RabbitMQ...${NC}"
    docker compose up -d 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ RabbitMQ iniciado (puerto 5672, dashboard: http://localhost:15672)${NC}"
        echo -e "  ${CYAN}Usuario: guest | Contraseña: guest${NC}"
    else
        echo -e "${RED}✗ Error al iniciar RabbitMQ${NC}"
        return 1
    fi
    
    # Esperar a que RabbitMQ esté listo
    echo -e "${YELLOW}▶ Esperando que RabbitMQ esté disponible (15 segundos para estabilizar)...${NC}"
    sleep 15
    echo ""
    
    # Iniciar Clientes
    echo -e "${YELLOW}▶ Iniciando Clientes (puerto 8000)${NC}"
    uvicorn serv_clientes:app --port 8000 --reload > /dev/null 2>&1 &
    CLIENTE_PID=$!
    echo -e "  ${GREEN}✓ PID: $CLIENTE_PID${NC}"
    sleep 1
    echo ""
    
    # Iniciar Productos
    echo -e "${YELLOW}▶ Iniciando Productos (puerto 8001)${NC}"
    uvicorn serv_productos:app --port 8001 --reload > /dev/null 2>&1 &
    PRODUCTO_PID=$!
    echo -e "  ${GREEN}✓ PID: $PRODUCTO_PID${NC}"
    sleep 1
    echo ""
    
    # Iniciar Pedidos
    echo -e "${YELLOW}▶ Iniciando Pedidos (puerto 8002)${NC}"
    uvicorn serv_pedidos:app --port 8002 --reload > /dev/null 2>&1 &
    PEDIDO_PID=$!
    echo -e "  ${GREEN}✓ PID: $PEDIDO_PID${NC}"
    sleep 1
    echo ""
    
    # Iniciar Inventario
    echo -e "${YELLOW}▶ Iniciando Inventario (puerto 8003)${NC}"
    uvicorn serv_inventario:app --port 8003 --reload > /dev/null 2>&1 &
    INVENTARIO_PID=$!
    echo -e "  ${GREEN}✓ PID: $INVENTARIO_PID${NC}"
    echo ""
    
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ Todos los servicios iniciados exitosamente${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}📊 DOCUMENTACIÓN SWAGGER:${NC}"
    echo -e "  • ${WHITE}Clientes${NC}:   ${CYAN}http://localhost:8000/docs${NC}"
    echo -e "  • ${WHITE}Productos${NC}:  ${CYAN}http://localhost:8001/docs${NC}"
    echo -e "  • ${WHITE}Pedidos${NC}:    ${CYAN}http://localhost:8002/docs${NC}"
    echo -e "  • ${WHITE}Inventario${NC}: ${CYAN}http://localhost:8003/docs${NC}"
    echo ""
    echo -e "${CYAN}🐰 RABBITMQ DASHBOARD:${NC}"
    echo -e "  • ${WHITE}URL${NC}:       ${CYAN}http://localhost:15672${NC}"
    echo -e "  • ${WHITE}Usuario${NC}:   ${CYAN}guest${NC}"
    echo -e "  • ${WHITE}Contraseña${NC}: ${CYAN}guest${NC}"
    echo ""
}

# ============================================================================
# FUNCIÓN: Detener servicios
# ============================================================================
detener_servicios() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}       DETENIENDO SHOPNOW${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Detener Clientes
    pkill -f "uvicorn serv_clientes:app"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Clientes (puerto 8000)${NC} - ${RED}Detenido${NC}"
    else
        echo -e "${YELLOW}○ Clientes (puerto 8000)${NC} - ${YELLOW}No estaba ejecutándose${NC}"
    fi
    
    # Detener Productos
    pkill -f "uvicorn serv_productos:app"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Productos (puerto 8001)${NC} - ${RED}Detenido${NC}"
    else
        echo -e "${YELLOW}○ Productos (puerto 8001)${NC} - ${YELLOW}No estaba ejecutándose${NC}"
    fi
    
    # Detener Pedidos
    pkill -f "uvicorn serv_pedidos:app"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Pedidos (puerto 8002)${NC} - ${RED}Detenido${NC}"
    else
        echo -e "${YELLOW}○ Pedidos (puerto 8002)${NC} - ${YELLOW}No estaba ejecutándose${NC}"
    fi
    
    # Detener Inventario
    pkill -f "uvicorn serv_inventario:app"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Inventario (puerto 8003)${NC} - ${RED}Detenido${NC}"
    else
        echo -e "${YELLOW}○ Inventario (puerto 8003)${NC} - ${YELLOW}No estaba ejecutándose${NC}"
    fi
    
    echo ""
    
    # Detener RabbitMQ
    echo -e "${YELLOW}▶ Deteniendo RabbitMQ...${NC}"
    docker compose down 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ RabbitMQ${NC} - ${RED}Detenido${NC}"
    else
        echo -e "${YELLOW}○ RabbitMQ${NC} - ${YELLOW}No pudo detenerse${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}✓ Todos los servicios han sido detenidos${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
}

# ============================================================================
# FUNCIÓN: Verificar estado de servicios
# ============================================================================
verificar_estado() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}       ESTADO DE SERVICIOS SHOPNOW${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Verificar RabbitMQ
    docker ps --filter "name=shopnow-rabbitmq" --quiet 2>/dev/null | grep -q .
    if [ $? -eq 0 ]; then
        CONTAINER_ID=$(docker ps --filter "name=shopnow-rabbitmq" --format "{{.ID}}" 2>/dev/null | head -1)
        echo -e "${GREEN}✓ RabbitMQ (puerto 5672)${NC} - ${GREEN}EJECUTÁNDOSE${NC}"
        echo -e "  ${CYAN}Container: ${CONTAINER_ID:0:12}${NC}"
        echo -e "  ${CYAN}Dashboard: http://localhost:15672${NC}"
    else
        echo -e "${RED}✗ RabbitMQ (puerto 5672)${NC} - ${RED}DETENIDO${NC}"
    fi
    echo ""
    
    # Verificar Clientes
    pgrep -f "uvicorn serv_clientes:app" > /dev/null
    if [ $? -eq 0 ]; then
        PID=$(pgrep -f "uvicorn serv_clientes:app")
        echo -e "${GREEN}✓ Clientes (puerto 8000)${NC} - ${GREEN}EJECUTÁNDOSE${NC} ${CYAN}(PID: $PID)${NC}"
    else
        echo -e "${RED}✗ Clientes (puerto 8000)${NC} - ${RED}DETENIDO${NC}"
    fi
    
    # Verificar Productos
    pgrep -f "uvicorn serv_productos:app" > /dev/null
    if [ $? -eq 0 ]; then
        PID=$(pgrep -f "uvicorn serv_productos:app")
        echo -e "${GREEN}✓ Productos (puerto 8001)${NC} - ${GREEN}EJECUTÁNDOSE${NC} ${CYAN}(PID: $PID)${NC}"
    else
        echo -e "${RED}✗ Productos (puerto 8001)${NC} - ${RED}DETENIDO${NC}"
    fi
    
    # Verificar Pedidos
    pgrep -f "uvicorn serv_pedidos:app" > /dev/null
    if [ $? -eq 0 ]; then
        PID=$(pgrep -f "uvicorn serv_pedidos:app")
        echo -e "${GREEN}✓ Pedidos (puerto 8002)${NC} - ${GREEN}EJECUTÁNDOSE${NC} ${CYAN}(PID: $PID)${NC}"
    else
        echo -e "${RED}✗ Pedidos (puerto 8002)${NC} - ${RED}DETENIDO${NC}"
    fi
    
    # Verificar Inventario
    pgrep -f "uvicorn serv_inventario:app" > /dev/null
    if [ $? -eq 0 ]; then
        PID=$(pgrep -f "uvicorn serv_inventario:app")
        echo -e "${GREEN}✓ Inventario (puerto 8003)${NC} - ${GREEN}EJECUTÁNDOSE${NC} ${CYAN}(PID: $PID)${NC}"
    else
        echo -e "${RED}✗ Inventario (puerto 8003)${NC} - ${RED}DETENIDO${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
}

# ============================================================================
# SCRIPT PRINCIPAL
# ============================================================================
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
        echo -e "${RED}Error: Opción no reconocida: $1${NC}"
        echo ""
        mostrar_ayuda
        exit 1
        ;;
esac