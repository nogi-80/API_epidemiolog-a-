# API Enfermedades Loreto

## Requisitos
- Python 3.11+
- Datos en una carpeta accesible por la API

## Variables de entorno
Se cargan desde `.env` automáticamente.

- DATA_DIR: carpeta con los archivos de datos
- DATA_FILE: csv de casos (default: casos_tia_por_anio_enfermedad_con_nombres.csv)
- GEOJSON_FILE: geojson distritos (default: loreto_distritos.geojson)
- SECRET_KEY: clave para firmar JWT
- TOKEN_EXPIRE_MINUTES: minutos de expiración del token
- BLACKLIST_FILE: archivo para persistir logout

## Ejecutar local
```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

## Autenticación
- `POST /login` con JSON `{ "email": "admin@admin.com", "password": "Admin123" }`
- Respuesta: `access_token` (Bearer)
- Usar header: `Authorization: Bearer <token>`
- `POST /logout` invalida el token actual

## Endpoints
- GET /health
- POST /login
- POST /logout
- GET /diseases?limit=100&offset=0
- GET /years
- GET /disease-codes?q=malaria
- GET /map?year=2025&code=B50
- GET /top?year=2025&code=B50&metric=tia&limit=10&offset=0
- GET /export?year=2025&code=B50&format=csv

## Tests
```bash
pip install -r requirements-dev.txt
pytest
```

## Docker
Montar los datos como volumen:
```bash
docker build -t api-enfermedades .
docker run -p 8000:8000 -e DATA_DIR=/data -e SECRET_KEY=mi-clave -e BLACKLIST_FILE=/app/token_blacklist.txt -v "G:\Mi unidad\ciencia de datos\todas_enfermedades\datos:/data" api-enfermedades
```

## docker-compose
```bash
docker compose up --build
```

Si estás en Windows, reemplaza el volumen del compose por la ruta completa de tus datos.
