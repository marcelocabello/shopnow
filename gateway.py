import json
import os
from typing import Dict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse, JSONResponse, Response


SERVICE_TARGETS: Dict[str, Dict[str, str]] = {
    "clientes": {
        "base_url": os.getenv("CLIENTES_URL", "http://127.0.0.1:8010"),
        "label": "Clientes",
    },
    "productos": {
        "base_url": os.getenv("PRODUCTOS_URL", "http://127.0.0.1:8001"),
        "label": "Productos",
    },
    "pedidos": {
        "base_url": os.getenv("PEDIDOS_URL", "http://127.0.0.1:8002"),
        "label": "Pedidos",
    },
    "inventario": {
        "base_url": os.getenv("INVENTARIO_URL", "http://127.0.0.1:8003"),
        "label": "Inventario",
    },
}
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

app = FastAPI(
    title="ShopNow Gateway",
    description=(
        "Gateway para exponer los 4 microservicios de ShopNow con una sola "
        "URL publica."
    ),
    version="1.0.0",
)


def _build_target_url(service_name: str, upstream_path: str, request: Request) -> str:
    base_url = SERVICE_TARGETS[service_name]["base_url"].rstrip("/")
    clean_path = upstream_path.lstrip("/")
    target_url = f"{base_url}/{clean_path}" if clean_path else base_url
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"
    return target_url


def _filter_request_headers(request: Request) -> Dict[str, str]:
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


def _filter_response_headers(headers) -> Dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


def _rewrite_docs_html(service_name: str, payload: bytes) -> bytes:
    text = payload.decode("utf-8")
    replacements = {
        '"/openapi.json"': f'"/{service_name}/openapi.json"',
        "'/openapi.json'": f"'/{service_name}/openapi.json'",
        '"/docs/oauth2-redirect"': f'"/{service_name}/docs/oauth2-redirect"',
        "'/docs/oauth2-redirect'": f"'/{service_name}/docs/oauth2-redirect'",
        '"/redoc"': f'"/{service_name}/redoc"',
        "'/redoc'": f"'/{service_name}/redoc'",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("utf-8")


def _rewrite_openapi_json(service_name: str, payload: bytes) -> bytes:
    data = json.loads(payload.decode("utf-8"))

    original_paths = data.get("paths", {})
    data["paths"] = {
        f"/{service_name}{path}": value for path, value in original_paths.items()
    }
    data["servers"] = [{"url": ""}]

    components = data.get("components", {})
    security_schemes = components.get("securitySchemes", {})
    for scheme in security_schemes.values():
        flows = scheme.get("flows", {})
        for flow in flows.values():
            token_url = flow.get("tokenUrl")
            if isinstance(token_url, str) and token_url.startswith("/"):
                flow["tokenUrl"] = f"/{service_name}{token_url}"

    return json.dumps(data, ensure_ascii=False).encode("utf-8")


async def _proxy_request(service_name: str, upstream_path: str, request: Request) -> Response:
    if service_name not in SERVICE_TARGETS:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    body = await request.body()
    target_url = _build_target_url(service_name, upstream_path, request)
    upstream_request = UrlRequest(
        target_url,
        data=body if body else None,
        headers=_filter_request_headers(request),
        method=request.method,
    )

    try:
        upstream_response = urlopen(upstream_request, timeout=30)
        payload = upstream_response.read()
        status_code = upstream_response.status
        response_headers = _filter_response_headers(upstream_response.headers)
    except HTTPError as exc:
        payload = exc.read()
        status_code = exc.code
        response_headers = _filter_response_headers(exc.headers)
    except URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo conectar con el servicio {SERVICE_TARGETS[service_name]['label']}: {exc.reason}",
        ) from exc

    content_type = response_headers.get("Content-Type", "")

    if upstream_path == "docs" and "text/html" in content_type:
        payload = _rewrite_docs_html(service_name, payload)
    elif upstream_path == "openapi.json" and "application/json" in content_type:
        payload = _rewrite_openapi_json(service_name, payload)
        response_headers["Content-Type"] = "application/json; charset=utf-8"

    return Response(content=payload, status_code=status_code, headers=response_headers)


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "mensaje": "Gateway publico de ShopNow",
            "gateway_docs": "/docs",
            "servicios": {
                name: {
                    "label": info["label"],
                    "url_base": info["base_url"],
                    "docs": f"/{name}/docs",
                    "openapi": f"/{name}/openapi.json",
                    "token": f"/{name}/token",
                }
                for name, info in SERVICE_TARGETS.items()
            },
        }
    )


@app.get("/panel", response_class=HTMLResponse)
def panel() -> str:
    cards = []
    for name, info in SERVICE_TARGETS.items():
        cards.append(
            f"""
            <li>
              <strong>{info['label']}</strong><br>
              Docs: <a href="/{name}/docs">/{name}/docs</a><br>
              OpenAPI: <a href="/{name}/openapi.json">/{name}/openapi.json</a><br>
              Token: <code>/{name}/token</code>
            </li>
            """
        )

    return f"""
    <!doctype html>
    <html lang="es">
      <head>
        <meta charset="utf-8">
        <title>ShopNow Gateway</title>
      </head>
      <body>
        <h1>ShopNow Gateway</h1>
        <p>Una sola URL publica para todos los microservicios.</p>
        <ul>
          {''.join(cards)}
        </ul>
      </body>
    </html>
    """


@app.get("/ui", response_class=FileResponse)
def ui_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/ui/app.js", response_class=FileResponse)
def ui_app_js():
    return FileResponse(FRONTEND_DIR / "app.js")


@app.api_route("/{service_name}", methods=ALL_METHODS)
async def proxy_service_root(service_name: str, request: Request) -> Response:
    return await _proxy_request(service_name, "", request)


@app.api_route("/{service_name}/{upstream_path:path}", methods=ALL_METHODS)
async def proxy_service_path(service_name: str, upstream_path: str, request: Request) -> Response:
    return await _proxy_request(service_name, upstream_path, request)
