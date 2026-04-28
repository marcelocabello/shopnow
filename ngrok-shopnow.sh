#!/bin/bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.ngrok-shopnow.pid"
LOG_FILE="$SCRIPT_DIR/.ngrok-shopnow.log"
URL_FILE="$SCRIPT_DIR/ngrok.txt"
API_URL="http://127.0.0.1:4040/api/tunnels"
DEFAULT_NGROK_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/ngrok/ngrok.yml"

print_usage() {
    cat <<'EOF'
Uso: ./ngrok-shopnow.sh [start|stop|status|urls]

Comandos:
  start   Inicia un tunel ngrok para el gateway local en 8090 y genera ngrok.txt
  stop    Detiene el tunel iniciado por este script
  status  Muestra el estado actual y las URLs disponibles
  urls    Regenera ngrok.txt a partir de la API local de ngrok
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "No se encontro el comando requerido: $cmd"
        exit 1
    fi
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid="$(cat "$PID_FILE")"
        if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

wait_for_api() {
    local retries=20
    local count=0

    while [ "$count" -lt "$retries" ]; do
        if curl -fsS "$API_URL" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    return 1
}

get_public_url() {
    local json public_url

    if ! json="$(curl -fsS "$API_URL")"; then
        return 1
    fi

    public_url="$(JSON_INPUT="$json" python3 <<'PY'
import json
import os

data = json.loads(os.environ["JSON_INPUT"])
public_url = ""
for tunnel in data.get("tunnels", []):
    candidate = tunnel.get("public_url", "")
    if candidate.startswith("https://"):
        public_url = candidate
        break
    if not public_url and candidate:
        public_url = candidate
print(public_url)
PY
)"

    if [ -z "$public_url" ]; then
        return 1
    fi

    printf '%s\n' "$public_url"
}

wait_for_public_url() {
    local retries=20
    local count=0

    while [ "$count" -lt "$retries" ]; do
        if get_public_url >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    return 1
}

write_urls_file() {
    local public_url

    if ! public_url="$(get_public_url)"; then
        echo "No hay un tunel publico activo reportado por ngrok."
        return 1
    fi


    cat > "$URL_FILE" <<EOF
NGROK - SHOPNOW
================

Gateway: $public_url
Panel: $public_url/panel
Gateway docs: $public_url/docs

Clientes docs: $public_url/clientes/docs
Productos docs: $public_url/productos/docs
Pedidos docs: $public_url/pedidos/docs
Inventario docs: $public_url/inventario/docs
EOF
}

start_ngrok() {
    require_command ngrok
    require_command curl
    require_command python3

    if is_running; then
        echo "Ya hay un tunel de ngrok iniciado por este script."
        echo "Revisa: $URL_FILE"
        exit 0
    fi

    rm -f "$PID_FILE" "$LOG_FILE" "$URL_FILE"

    local config_arg="$DEFAULT_NGROK_CONFIG"
    nohup ngrok http 8090 --config "$config_arg" --log "$LOG_FILE" > /dev/null 2>&1 &
    echo $! > "$PID_FILE"

    if ! wait_for_api; then
        echo "ngrok no respondio a tiempo. Revisa el log: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi

    if ! wait_for_public_url; then
        echo "ngrok respondio, pero no publico la URL a tiempo. Revisa el log: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi

    if ! write_urls_file; then
        echo "ngrok arranco, pero no pude generar $URL_FILE. Revisa el log: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi

    echo "Tunel creado correctamente."
    echo "Archivo generado: $URL_FILE"
    echo ""
    cat "$URL_FILE"
}

stop_ngrok() {
    if ! is_running; then
        echo "No hay un tunel activo iniciado por este script."
        rm -f "$PID_FILE"
        exit 0
    fi

    local pid
    pid="$(cat "$PID_FILE")"
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    rm -f "$PID_FILE"
    echo "Tunel de ngrok detenido."
}

status_ngrok() {
    if is_running; then
        echo "ngrok esta corriendo."
        if write_urls_file; then
            echo ""
            cat "$URL_FILE"
        else
            echo "No pude refrescar las URLs. Revisa el log: $LOG_FILE"
        fi
    else
        echo "ngrok no esta corriendo con este script."
    fi
}

case "${1:-}" in
    start)
        start_ngrok
        ;;
    stop)
        stop_ngrok
        ;;
    status)
        status_ngrok
        ;;
    urls)
        if write_urls_file; then
            cat "$URL_FILE"
        else
            echo "No pude generar $URL_FILE. Revisa el log: $LOG_FILE"
            exit 1
        fi
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
