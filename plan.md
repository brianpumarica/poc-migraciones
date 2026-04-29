Armar una Prueba de Concepto (PoC) aislada es el paso ideal antes de tocar la infraestructura real. El enfoque de "Migraciones 100% Generadas en CI/CD" requiere que el código base esté perfectamente configurado para que Alembic pueda leer los modelos y la base de datos sin problemas dentro del contenedor.

Para esta PoC, **no necesitamos Frontend**. Con levantar FastAPI, la base de datos PostgreSQL, y configurar Alembic para que haga el *diff* automático de los modelos `Empresa` y `Empleado`, será suficiente para probar tu flujo.

Aquí tienes el paso a paso para arrancar desde cero usando Docker.

### 1. Estructura de Archivos
Crea una carpeta llamada `poc-migraciones` y arma la siguiente estructura:

```text
poc-migraciones/
├── app/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   └── main.py
├── .env
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

### 2. Archivos de Configuración (Docker y Dependencias)

**`requirements.txt`**
```text
fastapi==0.104.1
uvicorn==0.24.0.post1
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1
```

**`Dockerfile`**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`docker-compose.yml`**
```yaml
version: '3.8'

services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: password
      POSTGRES_DB: poc_db
    ports:
      - "5432:5432"

  web:
    build: .
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://admin:password@db:5432/poc_db
    depends_on:
      - db
```

### 3. Código Base (FastAPI + SQLAlchemy)

**`app/database.py`**
```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/poc_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
```

**`app/models.py`**
(Aquí definimos la empresa y el empleado con pocos atributos iniciales).
```python
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)

    empleados = relationship("Empleado", back_populates="empresa")

class Empleado(Base):
    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))

    empresa = relationship("Empresa", back_populates="empleados")
```

**`app/main.py`**
```python
from fastapi import FastAPI
from app.database import engine
# Importante: No creamos las tablas aquí con Base.metadata.create_all(bind=engine)
# Dejaremos que Alembic se encargue de todo.

app = FastAPI(title="PoC Migraciones CI/CD")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "App corriendo"}
```

---

### 4. Inicializar y Configurar Alembic

Ahora levantamos los contenedores en segundo plano y configuramos Alembic desde adentro del contenedor web:

1. Inicia el entorno:
   ```bash
   docker-compose up -d
   ```
2. Inicializa Alembic dentro del contenedor web:
   ```bash
   docker-compose exec web alembic init alembic
   ```

Esto creará una carpeta `alembic` y un archivo `alembic.ini`. Debemos hacer **dos cambios críticos** para que Alembic entienda nuestros modelos y use la variable de entorno:

**A. Editar `alembic/env.py`**
Busca la sección donde dice `target_metadata = None` (cerca de la línea 21) y cámbiala por esto:
```python
import os
from app.database import Base
from app.models import Empresa, Empleado # Importa tus modelos

target_metadata = Base.metadata

# Forzar a Alembic a usar la variable de entorno DATABASE_URL
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
```

**B. Editar `alembic.ini`**
Busca la línea que dice `sqlalchemy.url = driver://user:pass@localhost/dbname` y **coméntala** o bórrala, ya que ahora lo inyectamos dinámicamente desde `env.py`.

---

### 5. Cómo probar tu flujo (Simulando el CI/CD)

En tu flujo de trabajo propuesto (Opción 3), el desarrollador solo cambia `models.py` y empuja a GitHub. El CI/CD se encarga del resto. Para simular qué hará GitHub Actions localmente, sigue estos pasos:

**Paso 1: Generar la migración (Lo que haría el Job 1 del CI/CD)**
```bash
docker-compose exec web alembic revision --autogenerate -m "Crear Empresa y Empleado"
```
*Verás que se genera un archivo en `alembic/versions/`. Este es el archivo que el CI/CD revisaría.*

**Paso 2: Generar el SQL para el "Gatekeeper" (Lo que el CI pondría en el Pull Request)**
```bash
docker-compose exec web alembic upgrade head --sql
```
*Esto imprimirá el código SQL puro en la terminal. En tu pipeline real, capturarías este output y lo enviarías como comentario al Pull Request para que el Tech Lead lo lea y apruebe.*

**Paso 3: Ejecutar la migración (Lo que haría el Job 2 tras la aprobación manual)**
```bash
docker-compose exec web alembic upgrade head
```
*Ahora tu base de datos PostgreSQL ya tiene las tablas reales.*

### 6. La Prueba de Fuego: Agregando Atributos

Para comprobar que el ciclo de vida funciona:
1. Abre `app/models.py`.
2. Añade un nuevo atributo a `Empleado`, por ejemplo: `rol = Column(String, nullable=True)`.
3. Vuelve a simular el pipeline en la terminal:
   ```bash
   docker-compose exec web alembic revision --autogenerate -m "Agregar rol a Empleado"
   docker-compose exec web alembic upgrade head --sql
   docker-compose exec web alembic upgrade head
   ```

Si todo esto funciona de manera fluida, tu stack está 100% listo para ser trasladado al `.github/workflows/deploy.yml` exacto que diseñaste en tu resumen ejecutivo.
```