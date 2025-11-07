from waitress import serve
import app

if __name__ == '__main__':
    # serve the Flask WSGI app object defined in app.py
    serve(app.app, host='0.0.0.0', port=8000)
