#!/bin/bash

# User Manager Deployment Script
set -e

echo "🚀 Starting User Manager deployment..."

# Crear directorio de logs
sudo mkdir -p /var/log
sudo touch /var/log/user_manager.log
sudo touch /var/log/user_manager_security.log
sudo chown microservice:microservice /var/log/user_manager*.log

# Cambiar al usuario del servicio
cd /opt/user_manager

# Instalar dependencias
pip3 install -r requirements.txt

# Configurar variables de entorno
export SECRET_KEY="change-this-in-production-$(openssl rand -base64 32)"
export DEBUG=False
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Ejecutar migraciones
python3 manage.py makemigrations
python3 manage.py migrate

# Crear superusuario (solo si no existe)
echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')" | python3 manage.py shell

# Crear usuarios de prueba
python3 manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()

test_users = [
    ('testuser1', 'test123'),
    ('testuser2', 'test123'),
    ('patient_user', 'patient123'),
]

for username, password in test_users:
    if not User.objects.filter(username=username).exists():
        User.objects.create_user(username=username, password=password)
        print(f"Created user: {username}")
EOF

# Iniciar servidor
echo "🎯 Starting User Manager server on port 8000..."
python3 manage.py runserver 0.0.0.0:8000