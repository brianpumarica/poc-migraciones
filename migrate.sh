#!/bin/bash

# Toma el primer argumento como mensaje, o usa "auto-migracion" por defecto
MESSAGE=${1:-"auto-migracion"}

echo "Generando migración: $MESSAGE..."
docker-compose exec web alembic revision --autogenerate -m "$MESSAGE"

echo "Aplicando migración a la base de datos..."
docker-compose exec web alembic upgrade head

echo "¡Migración completada con éxito!"
