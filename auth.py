"""
Módulo de autenticación JWT compartido para todos los servicios de ShopNow.

Uso en cada servicio:
    from auth import verificar_token, endpoint_login, Token

Credenciales disponibles:
    - admin / admin123
    - usuario / pass123
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

# ── Configuración ──────────────────────────────────────────────────────────────
SECRET_KEY = "shopnow-soa-secret-2024-querétaro"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# Usuarios en memoria (en producción usar base de datos con hashing)
USUARIOS_DB: dict = {
    "admin":   "admin123",
    "usuario": "pass123",
}

# Esquema OAuth2; el tokenUrl debe coincidir con el endpoint /token de cada servicio
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ── Modelos ────────────────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str


# ── Funciones de auth ──────────────────────────────────────────────────────────
def crear_token(username: str, expires_delta: Optional[timedelta] = None) -> str:
    """Genera un JWT firmado con HS256."""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependencia FastAPI que valida el Bearer token.
    Levanta 401 si el token es inválido o expirado.
    Retorna el nombre de usuario autenticado.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado. Obtenga uno con POST /token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise unauthorized
        return username
    except JWTError:
        raise unauthorized


def endpoint_login(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """
    Función lista para usar como handler del endpoint POST /token.
    Valida credenciales y retorna un JWT.
    """
    password = USUARIOS_DB.get(form_data.username)
    if password is None or password != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = crear_token(form_data.username)
    return Token(access_token=token, token_type="bearer")
