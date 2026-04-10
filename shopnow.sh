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

SERVICE_CLIENTES_CMD="uvicorn serv_clientes:app --port 8010 --reload"
SERVICE_PRODUCTOS_CMD="uvicorn serv_productos:app --port 8001 --reload"
SERVICE_PEDIDOS_CMD="uvicorn serv_pedidos:app --port 8002 --reload"
SERVICE_INVENTARIO_CMD="uvicorn serv_inventario:app --port 8003 --reload"

start_service() {
    local service_name="$1"
    local cmd="$2"
    local port="$3"
    local match="uvicorn ${service_name}:app"

    if pgrep -f "$match" > /dev/null; then
        echo -e "${YELLOW}○ ${service_name} ya está ejecutándose en ${port}${NC}"
        return 0
    fi

    nohup $cmd > /dev/null 2>&1 &
    local pid=$!
    echo -e "${GREEN}✓ ${service_name} iniciado (PID: ${pid}, puerto ${port})${NC}"
}

stop_service() {
    local service_name="$1"
    local port="$2"
    local match="uvicorn ${service_name}:app"

    if pkill -f "$match"; then
        echo -e "${GREEN}✓ ${service_name} detenido (puerto ${port})${NC}"
    else
        echo -e "${YELLOW}○ ${service_name} no estaba ejecutándose (puerto ${port})${NC}"
    fi
}

status_service() {
    local service_name="$1"
    local port="$2"
    local match="uvicorn ${service_name}:app"

    if pgrep -f "$match" > /dev/null; then
        local pid
        pid=$(pgrep -f "$match" | tr '\n' ' ')
        echo -e "${GREEN}✓ ${service_name}${NC} en puerto ${port} ${CYAN}(PID: ${pid})${NC}"
    else
        echo -e "${RED}✗ ${service_name}${NC} en puerto ${port} ${RED}(DETENIDO)${NC}"
    fi
}

mostrar_menu_runtime() {
    while true; do
        echo ""
        echo -e "${BLUE}════════════════ MENÚ DE CONTROL EN VIVO ════════════════${NC}"
        echo -e "${WHITE}1) Status de servicios${NC}"
        echo -e "${WHITE}2) Detener Clientes${NC}"
        echo -e "${WHITE}3) Iniciar Clientes${NC}"
        echo -e "${WHITE}4) Detener Productos${NC}"
        echo -e "${WHITE}5) Iniciar Productos${NC}"
        echo -e "${WHITE}6) Detener Pedidos${NC}"
        echo -e "${WHITE}7) Iniciar Pedidos${NC}"
        echo -e "${WHITE}8) Detener Inventario${NC}"
        echo -e "${WHITE}9) Iniciar Inventario${NC}"
        echo -e "${WHITE}10) Reiniciar RabbitMQ${NC}"
        echo -e "${WHITE}11) Salir del menú (servicios siguen corriendo)${NC}"
        echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
        read -r -p "Selecciona una opción [1-11]: " opcion

        case "$opcion" in
            1)
                verificar_estado
                ;;
            2)
                stop_service "serv_clientes" "8010"
                ;;
            3)
                start_service "serv_clientes" "$SERVICE_CLIENTES_CMD" "8010"
                ;;
            4)
                stop_service "serv_productos" "8001"
                ;;
            5)
                start_service "serv_productos" "$SERVICE_PRODUCTOS_CMD" "8001"
                ;;
            6)
                stop_service "serv_pedidos" "8002"
                ;;
            7)
                start_service "serv_pedidos" "$SERVICE_PEDIDOS_CMD" "8002"
                ;;
            8)
                stop_service "serv_inventario" "8003"
                ;;
            9)
                start_service "serv_inventario" "$SERVICE_INVENTARIO_CMD" "8003"
                ;;
            10)
                echo -e "${YELLOW}▶ Reiniciando RabbitMQ...${NC}"
                docker restart shopnow-rabbitmq > /dev/null 2>&1
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}✓ RabbitMQ reiniciado${NC}"
                else
                    echo -e "${RED}✗ No se pudo reiniciar RabbitMQ${NC}"
                fi
                ;;
            11)
                echo -e "${CYAN}Saliendo del menú. Los servicios permanecen ejecutándose.${NC}"
                break
                ;;
            *)
                echo -e "${RED}Opción inválida.${NC}"
                ;;
        esac
    done
}

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
    echo -e "  ${MAGENTA}Clientes${NC}:   puerto 8010"
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

    # Activar entorno virtual
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/.venv2/bin/activate"

    # Iniciar RabbitMQ (usa docker start sobre el contenedor existente)
    echo -e "${YELLOW}▶ Iniciando RabbitMQ...${NC}"
    docker start shopnow-rabbitmq > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓ RabbitMQ iniciado (puerto 5672, dashboard: http://localhost:15672)${NC}"
        echo -e "  ${CYAN}Usuario: guest | Contraseña: guest${NC}"
    else
        echo -e "  ${RED}✗ Error al iniciar RabbitMQ. ¿Existe el contenedor shopnow-rabbitmq?${NC}"
        echo -e "  ${YELLOW}  Crea el contenedor con: docker run -d --name shopnow-rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management${NC}"
        return 1
    fi
    echo -e "${YELLOW}▶ Esperando que RabbitMQ esté disponible...${NC}"
    sleep 8
    echo ""

    # Iniciar Clientes
    echo -e "${YELLOW}▶ Iniciando Clientes (puerto 8010)${NC}"
    start_service "serv_clientes" "$SERVICE_CLIENTES_CMD" "8010"
    sleep 1
    echo ""
    
    # Iniciar Productos
    echo -e "${YELLOW}▶ Iniciando Productos (puerto 8001)${NC}"
    start_service "serv_productos" "$SERVICE_PRODUCTOS_CMD" "8001"
    sleep 1
    echo ""
    
    # Iniciar Pedidos
    echo -e "${YELLOW}▶ Iniciando Pedidos (puerto 8002)${NC}"
    start_service "serv_pedidos" "$SERVICE_PEDIDOS_CMD" "8002"
    sleep 1
    echo ""
    
    # Iniciar Inventario
    echo -e "${YELLOW}▶ Iniciando Inventario (puerto 8003)${NC}"
    start_service "serv_inventario" "$SERVICE_INVENTARIO_CMD" "8003"
    echo ""
    
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ Todos los servicios iniciados exitosamente${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}📊 DOCUMENTACIÓN SWAGGER:${NC}"
    echo -e "  • ${WHITE}Clientes${NC}:   ${CYAN}http://localhost:8010/docs${NC}"
    echo -e "  • ${WHITE}Productos${NC}:  ${CYAN}http://localhost:8001/docs${NC}"
    echo -e "  • ${WHITE}Pedidos${NC}:    ${CYAN}http://localhost:8002/docs${NC}"
    echo -e "  • ${WHITE}Inventario${NC}: ${CYAN}http://localhost:8003/docs${NC}"
    echo ""
    echo -e "${CYAN}🐰 RABBITMQ DASHBOARD:${NC}"
    echo -e "  • ${WHITE}URL${NC}:       ${CYAN}http://localhost:15672${NC}"
    echo -e "  • ${WHITE}Usuario${NC}:   ${CYAN}guest${NC}"
    echo -e "  • ${WHITE}Contraseña${NC}: ${CYAN}guest${NC}"
    echo ""

    echo -e "${MAGENTA}Modo pruebas asíncronas:${NC} puedes detener/levantar servicios sin cerrar esta sesión."
    mostrar_menu_runtime
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
        echo -e "${GREEN}✓ Clientes (puerto 8010)${NC} - ${RED}Detenido${NC}"
    else
        echo -e "${YELLOW}○ Clientes (puerto 8010)${NC} - ${YELLOW}No estaba ejecutándose${NC}"
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
    docker stop shopnow-rabbitmq > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ RabbitMQ${NC} - ${RED}Detenido${NC}"
    else
        echo -e "${YELLOW}○ RabbitMQ${NC} - ${YELLOW}No estaba ejecutándose${NC}"
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
        echo -e "${GREEN}✓ Clientes (puerto 8010)${NC} - ${GREEN}EJECUTÁNDOSE${NC} ${CYAN}(PID: $PID)${NC}"
    else
        echo -e "${RED}✗ Clientes (puerto 8010)${NC} - ${RED}DETENIDO${NC}"
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