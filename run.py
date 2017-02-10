import os

from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', app.config["WEB_SERVER_PORT"]))
    app.run(host='0.0.0.0', port=port)
