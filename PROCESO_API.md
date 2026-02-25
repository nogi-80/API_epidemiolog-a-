# Documento del Proyecto: API de Enfermedades (Loreto)

## Objetivo
Crear una API en FastAPI para exponer datos de enfermedades de Loreto (Perú) con endpoints para:
- Listar enfermedades y años disponibles.
- Entregar un GeoJSON unido con métricas (CASOS/POBTOT/TIA) para mapa de calor.
- Mostrar el top de distritos por métrica.
- Exportar resultados en CSV.

## Resumen del flujo de trabajo
1. Revisamos la carpeta del proyecto en `G:\Mi unidad\ciencia de datos\todas_enfermedades`.
2. Identificamos los datos principales y los scripts de procesamiento.
3. Definimos los endpoints de la API y su comportamiento.
4. Elegimos FastAPI y una ruta de datos configurable para que sea multiplataforma.
5. Construimos la API, documentación, Dockerfile y docker-compose.
6. Agregamos CORS, paginación, búsqueda de códigos y tests.

## Datos del proyecto
Los datos usados por la API están en:
- `G:\Mi unidad\ciencia de datos\todas_enfermedades\datos`

Archivos principales:
- `casos_tia_por_anio_enfermedad_con_nombres.csv`
  Contiene columnas `ANO`, `UBIGEO`, `DIAGNOSTIC`, `CASOS`, `POBTOT`, `TIA`, `ENFERMEDAD`.
- `loreto_distritos.geojson`
  GeoJSON de distritos de Loreto con campo `UBIGEO` para el cruce.

## Estructura de la API
Carpeta creada: `G:\Mi unidad\ciencia de datos\todas_enfermedades\api`

Contenido:
- `app/main.py`
  Código principal de la API. Carga los datos, aplica filtros, une GeoJSON y expone endpoints.
  Incluye:
  - CORS configurable por `ALLOWED_ORIGINS`.
  - Paginación con `limit` y `offset`.
  - Endpoint de búsqueda `/disease-codes`.

- `app/__init__.py`
  Archivo vacío para tratar `app` como paquete Python.

- `requirements.txt`
  Dependencias mínimas para ejecutar la API:
  - `fastapi`, `uvicorn`, `pandas`.

- `requirements-dev.txt`
  Dependencias para pruebas:
  - `pytest`, `httpx`.

- `.env.example`
  Ejemplo de variables de entorno:
  - `DATA_DIR`: carpeta con datos.
  - `DATA_FILE`: CSV principal.
  - `GEOJSON_FILE`: GeoJSON de distritos.

- `Dockerfile`
  Permite construir la imagen Docker de la API.

- `docker-compose.yml`
  Levanta la API con volumen de datos montado.

- `README.md`
  Instrucciones de uso local, Docker, endpoints y tests.

- `tests/`
  Pruebas automáticas con datos mínimos de ejemplo:
  - `tests/test_api.py`
  - `tests/data/casos_tia_por_anio_enfermedad_con_nombres.csv`
  - `tests/data/loreto_distritos.geojson`

## Endpoints definidos
- `GET /health`
  Estado de la API.

- `GET /diseases?limit=100&offset=0`
  Lista de enfermedades disponibles (código + nombre).

- `GET /years`
  Lista de años disponibles.

- `GET /disease-codes?q=malaria&limit=100&offset=0`
  Búsqueda por nombre o código.

- `GET /map?year=2025&code=B50`
  Devuelve un GeoJSON unido con datos de `CASOS`, `POBTOT`, `TIA`.

- `GET /top?year=2025&code=B50&metric=tia&limit=10&offset=0`
  Top de distritos ordenados por `tia`, `casos` o `pobtot`.

- `GET /export?year=2025&code=B50&format=csv`
  Exporta CSV con los datos agregados por distrito.

## Variables de entorno
- `DATA_DIR`: carpeta con datos (configurable para servidor o Docker).
- `DATA_FILE`: nombre del CSV principal (default `casos_tia_por_anio_enfermedad_con_nombres.csv`).
- `GEOJSON_FILE`: nombre del GeoJSON de Loreto (default `loreto_distritos.geojson`).
- `ALLOWED_ORIGINS`: CORS ("*" o lista separada por comas).

## Cómo ejecutar local
```bash
pip install -r requirements.txt
set DATA_DIR=G:\Mi unidad\ciencia de datos\todas_enfermedades\datos
uvicorn app.main:app --reload
```

## Docker
```bash
docker build -t api-enfermedades .
docker run -p 8000:8000 -e DATA_DIR=/data -v "G:\Mi unidad\ciencia de datos\todas_enfermedades\datos:/data" api-enfermedades
```

## docker-compose
```bash
docker compose up --build
```

## Notas
- La API está enfocada en Loreto porque el GeoJSON y los datos están filtrados a UBIGEO que empieza con `16`.
- Para ampliar a todo Perú se requiere un GeoJSON nacional y datos sin filtro por Loreto.
