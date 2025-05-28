#!/bin/bash

# Patient Manager Deployment Script
set -e

echo "🏥 Starting Patient Manager deployment..."

# Crear directorios necesarios
sudo mkdir -p /opt/patient_manager/logs
sudo chown -R microservice:microservice /opt/patient_manager

# Cambiar al usuario del servicio
cd /opt/patient_manager

# Instalar dependencias
pip3 install -r requirements.txt

# Configurar variables de entorno
export SECRET_KEY="patient-manager-$(openssl rand -base64 32)"
export DEBUG=False
export DB_HOST=${POSTGRES_INTERNAL_IP}
export DB_NAME=patients_db
export DB_USER=postgres
export DB_PASSWORD=postgres123
export DB_PORT=5432
export MEMCACHED_LOCATION=127.0.0.1:11211

# Ejecutar migraciones
python3 manage.py makemigrations
python3 manage.py migrate

# Poblar base de datos con datos de prueba
echo "🔄 Populating database with test data..."
python3 manage.py populate_patients --patients 1000 --records 5000

# Iniciar servidor
echo "🎯 Starting Patient Manager server on port 8001..."
python3 manage.py runserver 0.0.0.0:8001