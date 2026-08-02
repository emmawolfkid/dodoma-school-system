"""
Production entry point -- runs the app under waitress instead of
`manage.py runserver` (which is single-threaded and not meant for real
traffic). Works the same on Windows and Linux.

Usage:
    python run_production.py

Reads HOST/PORT/THREADS from the environment so it can be tuned per
deployment without editing code:
    DJANGO_SERVE_HOST   (default 0.0.0.0)
    DJANGO_SERVE_PORT   (default 8000)
    DJANGO_SERVE_THREADS (default 8)

Remember: DJANGO_DEBUG=False and a real DJANGO_SECRET_KEY must be set
in the environment before running this for real -- see DEPLOYMENT.md.
"""
import os

import django
from waitress import serve

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from config.wsgi import application  # noqa: E402

if __name__ == '__main__':
    host = os.environ.get('DJANGO_SERVE_HOST', '0.0.0.0')
    port = int(os.environ.get('DJANGO_SERVE_PORT', '8000'))
    threads = int(os.environ.get('DJANGO_SERVE_THREADS', '8'))

    print(f"Serving on http://{host}:{port} with {threads} threads (waitress)")
    serve(application, host=host, port=port, threads=threads)
