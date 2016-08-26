import os
from webServer import app
from config import *

if __name__ == '__main__':
    port = int(os.environ.get('PORT', IKY_PORT))
    app.run(host='0.0.0.0', port=port,threaded=True, debug='True')
