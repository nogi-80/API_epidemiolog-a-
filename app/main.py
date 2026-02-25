from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel


load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_FILE = os.getenv("DATA_FILE", "casos_tia_por_anio_enfermedad_con_nombres.csv")
GEOJSON_FILE = os.getenv("GEOJSON_FILE", "loreto_distritos.geojson")

SECRET_KEY = os.getenv("SECRET_KEY", "y9pZ5g7rQ2nL1uM8vX6dA0sK4eT3bH9c")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "60"))
BLACKLIST_FILE = Path(os.getenv("BLACKLIST_FILE", "./token_blacklist.txt"))

ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "Admin123"


security = HTTPBearer()


def load_blacklist() -> set[str]:
    if not BLACKLIST_FILE.exists():
        return set()
    return {line.strip() for line in BLACKLIST_FILE.read_text(encoding="utf-8").splitlines() if line.strip()}


def blacklist_token(token: str) -> None:
    BLACKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with BLACKLIST_FILE.open("a", encoding="utf-8") as f:
        f.write(token + "\n")


token_blacklist: set[str] = load_blacklist()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@dataclass(frozen=True)
class DataBundle:
    df: pd.DataFrame
    geojson: Dict
    ubigeo_to_name: Dict[str, str]
    disease_pairs: List[Tuple[str, str]]
    years: List[int]


@lru_cache(maxsize=1)
def load_data() -> DataBundle:
    data_path = DATA_DIR / DATA_FILE
    geo_path = DATA_DIR / GEOJSON_FILE

    if not data_path.exists():
        raise FileNotFoundError(f"No existe el archivo de datos: {data_path}")
    if not geo_path.exists():
        raise FileNotFoundError(f"No existe el GeoJSON: {geo_path}")

    df = pd.read_csv(data_path, low_memory=False)
    required = {"ANO", "UBIGEO", "DIAGNOSTIC", "CASOS", "POBTOT", "TIA", "ENFERMEDAD"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {sorted(missing)}")

    df["UBIGEO"] = df["UBIGEO"].astype(str).str.zfill(6)
    df["ANO"] = pd.to_numeric(df["ANO"], errors="coerce")
    df["CASOS"] = pd.to_numeric(df["CASOS"], errors="coerce")
    df["POBTOT"] = pd.to_numeric(df["POBTOT"], errors="coerce")

    with geo_path.open(encoding="utf-8-sig") as f:
        geojson = json.load(f)

    ubigeo_to_name = {}
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        ub = str(props.get("UBIGEO", "")).zfill(6)
        if ub:
            ubigeo_to_name[ub] = props.get("NOMBDIST", "")

    disease_pairs = (
        df[["DIAGNOSTIC", "ENFERMEDAD"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["DIAGNOSTIC", "ENFERMEDAD"])
    )
    disease_list = [(row.DIAGNOSTIC, row.ENFERMEDAD) for row in disease_pairs.itertuples(index=False)]

    years = (
        df["ANO"]
        .dropna()
        .astype(int)
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    return DataBundle(df=df, geojson=geojson, ubigeo_to_name=ubigeo_to_name, disease_pairs=disease_list, years=years)


def filter_by_year_code(df: pd.DataFrame, year: int, code: str) -> pd.DataFrame:
    out = df[(df["ANO"] == year) & (df["DIAGNOSTIC"] == code)].copy()
    if out.empty:
        return out

    grouped = out.groupby("UBIGEO", as_index=False).agg({
        "CASOS": "sum",
        "POBTOT": "mean",
    })
    grouped["TIA"] = (grouped["CASOS"] / grouped["POBTOT"]) * 1000
    return grouped


def merge_geojson(geojson: Dict, data: pd.DataFrame) -> Dict:
    values = data.set_index("UBIGEO").to_dict(orient="index") if not data.empty else {}
    merged = json.loads(json.dumps(geojson))

    for feat in merged.get("features", []):
        props = feat.get("properties", {})
        ub = str(props.get("UBIGEO", "")).zfill(6)
        row = values.get(ub)
        if row:
            props.update({
                "CASOS": float(row.get("CASOS")) if row.get("CASOS") is not None else None,
                "POBTOT": float(row.get("POBTOT")) if row.get("POBTOT") is not None else None,
                "TIA": float(row.get("TIA")) if row.get("TIA") is not None else None,
            })
        else:
            props.update({"CASOS": None, "POBTOT": None, "TIA": None})
        feat["properties"] = props

    return merged


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    if token in token_blacklist:
        raise HTTPException(status_code=401, detail="Token inválido")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token inválido")
    return sub


app = FastAPI(title="API Enfermedades Loreto", version="1.3.3")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    if payload.email != ADMIN_EMAIL or payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_access_token(payload.email)
    return TokenResponse(access_token=token, expires_in=TOKEN_EXPIRE_MINUTES * 60)


@app.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, str]:
    token = credentials.credentials
    if token not in token_blacklist:
        token_blacklist.add(token)
        blacklist_token(token)
    return {"status": "ok"}


@app.get("/diseases")
def diseases(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: str = Depends(get_current_user),
) -> List[Dict[str, str]]:
    bundle = load_data()
    pairs = bundle.disease_pairs[offset : offset + limit]
    return [{"code": code, "name": name} for code, name in pairs]


@app.get("/years")
def years(user: str = Depends(get_current_user)) -> List[int]:
    bundle = load_data()
    return bundle.years


@app.get("/disease-codes")
def disease_codes(
    q: str | None = Query(None, description="Búsqueda por nombre o código"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: str = Depends(get_current_user),
) -> List[Dict[str, str]]:
    bundle = load_data()
    pairs = bundle.disease_pairs

    if q:
        ql = q.lower().strip()
        pairs = [
            (code, name)
            for code, name in pairs
            if ql in str(code).lower() or ql in str(name).lower()
        ]

    pairs = pairs[offset : offset + limit]
    return [{"code": code, "name": name} for code, name in pairs]


@app.get("/map")
def map_geojson(
    year: int = Query(...),
    code: str = Query(...),
    user: str = Depends(get_current_user),
) -> JSONResponse:
    bundle = load_data()
    if year not in bundle.years:
        raise HTTPException(status_code=404, detail="Año no encontrado")
    codes = {c for c, _ in bundle.disease_pairs}
    if code not in codes:
        raise HTTPException(status_code=404, detail="Código de enfermedad no encontrado")

    filtered = filter_by_year_code(bundle.df, year, code)
    merged = merge_geojson(bundle.geojson, filtered)
    return JSONResponse(content=merged)


@app.get("/top")
def top_districts(
    year: int = Query(...),
    code: str = Query(...),
    metric: str = Query("tia"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: str = Depends(get_current_user),
) -> List[Dict[str, object]]:
    bundle = load_data()
    if year not in bundle.years:
        raise HTTPException(status_code=404, detail="Año no encontrado")
    codes = {c for c, _ in bundle.disease_pairs}
    if code not in codes:
        raise HTTPException(status_code=404, detail="Código de enfermedad no encontrado")

    metric = metric.lower()
    allowed = {"tia", "casos", "pobtot"}
    if metric not in allowed:
        raise HTTPException(status_code=400, detail=f"metric debe ser uno de: {sorted(allowed)}")

    data = filter_by_year_code(bundle.df, year, code)
    if data.empty:
        return []

    data = data.sort_values(metric.upper(), ascending=False)
    if offset:
        data = data.iloc[offset:]
    data = data.head(limit)

    out = []
    for row in data.itertuples(index=False):
        ub = str(row.UBIGEO).zfill(6)
        out.append({
            "ubigeo": ub,
            "district": bundle.ubigeo_to_name.get(ub, ""),
            "casos": float(row.CASOS) if row.CASOS is not None else None,
            "pobtot": float(row.POBTOT) if row.POBTOT is not None else None,
            "tia": float(row.TIA) if row.TIA is not None else None,
        })
    return out


@app.get("/export")
def export_csv(
    year: int = Query(...),
    code: str = Query(...),
    format: str = Query("csv"),
    user: str = Depends(get_current_user),
) -> StreamingResponse:
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="format soportado: csv")

    bundle = load_data()
    if year not in bundle.years:
        raise HTTPException(status_code=404, detail="Año no encontrado")
    codes = {c for c, _ in bundle.disease_pairs}
    if code not in codes:
        raise HTTPException(status_code=404, detail="Código de enfermedad no encontrado")

    data = filter_by_year_code(bundle.df, year, code)

    def iter_rows() -> Iterable[str]:
        header = ["ANO", "UBIGEO", "CASOS", "POBTOT", "TIA"]
        yield ",".join(header) + "\n"
        if data.empty:
            return
        for row in data.itertuples(index=False):
            yield f"{year},{row.UBIGEO},{row.CASOS},{row.POBTOT},{row.TIA}\n"

    return StreamingResponse(iter_rows(), media_type="text/csv")

