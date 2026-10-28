#!/bin/bash

echo "📥 Pulling latest changes..."
git pull origin main

echo "📦 Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "🗄️ Running migrations..."
python manage.py migrate

echo "🖼️ Collecting static files..."
python manage.py collectstatic --noinput

echo "🔄 Restarting Gunicorn..."
sudo systemctl restart gunicorn

echo "✅ Deployment complete!"