Armar una Prueba de Concepto (PoC) aislada es el paso ideal antes de tocar la infraestructura real. El enfoque de "Migraciones 100% Generadas en CI/CD" requiere que el código base esté perfectamente configurado para que Alembic pueda leer los modelos y la base de datos sin problemas dentro del contenedor.

Para esta PoC, **no necesitamos Frontend**. Con levantar FastAPI, la base de datos PostgreSQL, y configurar Alembic para que haga el *diff* automático de los modelos `Empresa` y `Empleado`, será suficiente para probar tu flujo.

---

### 1. Inicializar y Configurar Alembic

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

### 2. Cómo probar tu flujo (Simulando el CI/CD)

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
*Esto imprimirá el código SQL puro en la terminal. En tu pipeline real, capturarías este output y lo enviarías como comentario al Pull Request para que el Tech Lead lo lea y apruebe - Actualmente, ya está implementado en github*

**Paso 3: Ejecutar la migración (Lo que haría el Job 2 tras la aprobación manual)**
```bash
docker-compose exec web alembic upgrade head
```
*Ahora tu base de datos PostgreSQL ya tiene las tablas reales.*

---

### 3. Configurar Gatekeeper en GitHub (Pipeline CI/CD)

Para usar el workflow del "Gatekeeper" (`pr_gatekeeper.yml`) y permitir que GitHub publique automáticamente el SQL generado en tus Pull Requests, asegúrate de:
1. Iniciar git y subir el código incluyendo `.github/workflows/pr_gatekeeper.yml`, `.gitignore` y `alembic/`.
2. **Dar permisos al Bot de GitHub**:
   - En tu repositorio remoto ve a **Settings** > **Actions** > **General**.
   - Baja hasta **Workflow permissions**.
   - Marca **"Read and write permissions"** y guarda. Esto permite a la acción `sticky-pull-request-comment` escribir en tu PR.

---

### 4. Configurar Gatekeeper en GitHub (Pipeline CI/CD)

Para usar el workflow del "Gatekeeper" (`pr_gatekeeper.yml`) y permitir que GitHub publique automáticamente el SQL generado en tus Pull Requests, asegúrate de:
1. Iniciar git y subir el código incluyendo `.github/workflows/pr_gatekeeper.yml`, `.gitignore` y `alembic/`.
2. **Dar permisos al Bot de GitHub**:
   - En tu repositorio remoto ve a **Settings** > **Actions** > **General**.
   - Baja hasta **Workflow permissions**.
   - Marca **"Read and write permissions"** y guarda. Esto permite a la acción `sticky-pull-request-comment` escribir en tu PR.

---
### 5. Pruebas de Estrés y Casos Extremos ("Rompiendo" Alembic)

Para asegurar que el enfoque 100% automatizado con CI/CD es robusto, ejecutaremos las siguientes pruebas de estrés para entender las limitaciones del `autogenerate` de Alembic y cómo el "Gatekeeper" evita desastres en Producción:

**Prueba 1: Renombrar una Columna (Riesgo de Pérdida de Datos)**
*   **Acción:** Cambiar el nombre de `rol` a `cargo` en el modelo `Empleado`.
*   **Hipótesis:** Alembic no sabe si renombraste el campo o si borraste uno viejo y creaste uno nuevo. Por defecto, generará un `DROP COLUMN rol` y un `ADD COLUMN cargo`. Esto significa que perderías toda la data.
*   **Solución:** El Tech Lead detectará el `DROP` en el Pull Request. Se debe intervenir la migración manualmente usando `op.alter_column()`.
*   **Estado:** Ejecutado y validado. La intervención manual funcionó correctamente.

**Prueba 2: Columna NOT NULL sin default en tabla con datos**
*   **Acción:** Insertar un dato en BD. Luego, en `Empleado` agregar `email = Column(String, nullable=False)`.
*   **Hipótesis:** Alembic autogenerará un `ADD COLUMN email VARCHAR NOT NULL`. Sin embargo, PostgreSQL abortará el `upgrade` porque ya existen filas y el nuevo campo no puede quedar vacío.
*   **Estado:** Ejecutado y validado. Al autogenerar la migración, Alembic creó correctamente los comandos `op.add_column` y `op.drop_column`. Sin embargo, al intentar aplicarla, PostgreSQL abortó el upgrade lanzando la excepción: `psycopg2.errors.NotNullViolation: column "email" of relation "empleados" contains null values`.
*   **Solución:** Intervenir manualmente la migración autogenerada aplicando uno de estos dos enfoques:
    1. **Migración en 3 pasos:** Modificar el archivo para crear la columna temporalmente con `nullable=True`, ejecutar un comando `op.execute("UPDATE empleados SET email = 'pendiente' WHERE email IS NULL")` para rellenar los datos existentes, y finalmente usar `op.alter_column` para aplicar la restricción `nullable=False`.
    2. **Parámetro server_default:** Agregar `server_default='sin_email@ejemplo.com'` dentro del `op.add_column` para que PostgreSQL llene automáticamente las filas existentes al crear la columna.

**Prueba 3: Cambio Incompatible de Tipo de Dato**
*   **Acción:** Cambiar el tipo de `rol` de `String` a `Integer`.
*   **Hipótesis:** Si la columna tiene letras, PostgreSQL rechazará el `ALTER TABLE ... TYPE INTEGER` porque no sabe cómo "castear" el texto a número.
*   **Solución:** Intervenir la migración para inyectar una cláusula `USING` de Postgres.

**Prueba 4: Renombrar una Tabla Completa**
*   **Acción:** Cambiar `__tablename__ = "empleados"` a `__tablename__ = "trabajadores"`.
*   **Hipótesis:** Alembic hará un `DROP TABLE empleados` y un `CREATE TABLE trabajadores`, rompiendo foreign keys y borrando datos.
*   **Solución:** Ajuste manual en la migración usando `op.rename_table()`.
```