"""WSGI entry point for production servers.

Most hosts (Gunicorn, uWSGI, etc.) can import this module and use the
`app` callable. We import the Flask `app` object defined in `app.py`.
"""
from app import app

# Expose as 'app' (module-level) for Gunicorn: `wsgi:app`

if __name__ == '__main__':
    # Fallback quick-run using Waitress for local Windows testing
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=8000)
    except Exception:
        # Last-resort: Flask's built-in server (not for production)
        app.run(host='0.0.0.0', port=8000)
