#!/bin/bash

# Script para gestionar el servicio Inventario Java
# Uso: ./java.sh [start|stop|status|logs]

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAVA_SERVICE_DIR="$SCRIPT_DIR/java-inventario"
JAVA_LOG_FILE="/tmp/inventario-java.log"
JAVA_PORT="8003"
JAR_NAME="inventario-java-1.0.0.jar"
JAR_PATH="$JAVA_SERVICE_DIR/target/$JAR_NAME"
PID_MATCH="java .*${JAR_NAME}"

resolver_java_cmd() {
    if [ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ]; then
        echo "$JAVA_HOME/bin/java"
        return 0
    fi

    if [ -x "/home/olecram/.jdk/jdk-25/bin/java" ]; then
        echo "/home/olecram/.jdk/jdk-25/bin/java"
        return 0
    fi

    if command -v java >/dev/null 2>&1; then
        command -v java
        return 0
    fi

    return 1
}

inventario_python_activo() {
    pgrep -f "uvicorn serv_inventario:app" >/dev/null 2>&1
}

java_activo() {
    pgrep -f "$PID_MATCH" >/dev/null 2>&1
}

mostrar_ayuda() {
    echo -e "${CYAN}Uso: ./java.sh [start|stop|status|logs]${NC}"
    echo ""
    echo -e "${WHITE}Opciones:${NC}"
    echo -e "  ${GREEN}start${NC}  - Inicia Inventario Java en puerto 8003"
    echo -e "  ${RED}stop${NC}   - Detiene Inventario Java"
    echo -e "  ${BLUE}status${NC} - Muestra estado de Inventario Java"
    echo -e "  ${CYAN}logs${NC}   - Muestra logs en vivo"
}

iniciar_java() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}       INICIANDO INVENTARIO JAVA${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

    if java_activo; then
        local pid
        pid=$(pgrep -f "$PID_MATCH" | tr '\n' ' ')
        echo -e "${YELLOW}○ Inventario Java ya está ejecutándose${NC} ${CYAN}(PID: ${pid})${NC}"
        echo -e "${CYAN}Swagger: http://localhost:${JAVA_PORT}/docs${NC}"
        return 0
    fi

    if inventario_python_activo; then
        echo -e "${YELLOW}▶ Detectado Inventario Python en puerto ${JAVA_PORT}. Deteniéndolo...${NC}"
        pkill -f "uvicorn serv_inventario:app"
        sleep 1
    fi

    if [ ! -f "$JAR_PATH" ]; then
        echo -e "${RED}✗ No se encontró el JAR: ${JAR_PATH}${NC}"
        echo -e "${YELLOW}  Compílalo con:${NC}"
        echo -e "  ${WHITE}cd ${JAVA_SERVICE_DIR} && mvn clean package -DskipTests${NC}"
        return 1
    fi

    local java_cmd
    java_cmd=$(resolver_java_cmd)
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ No se encontró Java (JAVA_HOME ni java en PATH)${NC}"
        return 1
    fi

    cd "$JAVA_SERVICE_DIR" || return 1
    nohup "$java_cmd" -jar "$JAR_PATH" > "$JAVA_LOG_FILE" 2>&1 &
    local pid=$!

    sleep 2
    if java_activo; then
        echo -e "${GREEN}✓ Inventario Java iniciado (PID: ${pid}, puerto ${JAVA_PORT})${NC}"
        echo -e "${CYAN}Swagger: http://localhost:${JAVA_PORT}/docs${NC}"
        echo -e "${CYAN}Logs: ${JAVA_LOG_FILE}${NC}"
        return 0
    fi

    echo -e "${RED}✗ Falló el inicio de Inventario Java. Revisa logs:${NC} ${JAVA_LOG_FILE}"
    return 1
}

detener_java() {
    echo ""
    if pkill -f "$PID_MATCH"; then
        echo -e "${GREEN}✓ Inventario Java detenido (puerto ${JAVA_PORT})${NC}"
    else
        echo -e "${YELLOW}○ Inventario Java no estaba ejecutándose${NC}"
    fi
}

estado_java() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}       ESTADO INVENTARIO JAVA${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

    if java_activo; then
        local pid
        pid=$(pgrep -f "$PID_MATCH" | tr '\n' ' ')
        echo -e "${GREEN}✓ Inventario Java${NC} - ${GREEN}EJECUTÁNDOSE${NC} ${CYAN}(PID: ${pid})${NC}"
        echo -e "${CYAN}URL: http://localhost:${JAVA_PORT}/docs${NC}"
    else
        echo -e "${RED}✗ Inventario Java${NC} - ${RED}DETENIDO${NC}"
    fi

    if inventario_python_activo; then
        echo -e "${YELLOW}○ Inventario Python también detectado en ejecución${NC}"
    fi
}

ver_logs() {
    if [ ! -f "$JAVA_LOG_FILE" ]; then
        echo -e "${YELLOW}No existe archivo de log aún: ${JAVA_LOG_FILE}${NC}"
        return 0
    fi

    tail -f "$JAVA_LOG_FILE"
}

if [ $# -eq 0 ]; then
    mostrar_ayuda
    exit 0
fi

case "$1" in
    start)
        iniciar_java
        ;;
    stop)
        detener_java
        ;;
    status)
        estado_java
        ;;
    logs)
        ver_logs
        ;;
    *)
        echo -e "${RED}Error: opción no reconocida: $1${NC}"
        mostrar_ayuda
        exit 1
        ;;
esac
