"""
WSGI entry point for gunicorn.

Usage: gunicorn -b 0.0.0.0:5000 wsgi:app
"""

from app import create_app

app = create_app()