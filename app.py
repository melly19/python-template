import logging
import socket

from routes import app
from routes.api_gateway import api_gateway_bp
from routes.toolbox1 import toolbox1_bp
from routes.showdown import showdown_bp
from routes.api_gateway_v2 import api_gateway_bp_v2

logger = logging.getLogger(__name__)
# app.register_blueprint(api_gateway_bp)
app.register_blueprint(showdown_bp)
app.register_blueprint(toolbox1_bp)
app.register_blueprint(api_gateway_bp_v2)

@app.route('/', methods=['GET'])
def default_route():
    return 'Python Template'

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

if __name__ == "__main__":
    logging.info("Starting application ...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 8080))
    port = sock.getsockname()[1]
    sock.close()
    app.run(port=port)
