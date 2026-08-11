import logging

from a2wsgi import WSGIMiddleware
from starlette.routing import Mount

from routes import app
from routes.api_gateway import api_gateway_bp
from routes.toolbox1 import mcp
from routes.toolbox1 import toolbox1_bp
from routes.showdown import showdown_bp
from routes.square import square_bp
from routes.api_gateway_v2 import api_gateway_bp_v2
from routes.ghost_chains import ghost_chains_bp

logger = logging.getLogger(__name__)
app.register_blueprint(api_gateway_bp)
app.register_blueprint(showdown_bp)
app.register_blueprint(toolbox1_bp)
app.register_blueprint(api_gateway_bp_v2)
app.register_blueprint(ghost_chains_bp)
app.register_blueprint(square_bp)

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

# Flask is WSGI, but mcp.http_app() is an ASGI (Starlette) app, so the ASGI app
# has to be the outer one -- a WSGI app cannot host an ASGI app. FastMCP serves
# the exact path /mcp; everything else falls through to Flask via a WSGI bridge.
mcp_app = mcp.http_app(path="/mcp")
mcp_app.router.routes.append(Mount("/", app=WSGIMiddleware(app)))

# This is the entry point for gunicorn/uvicorn, not the Flask app.
asgi_app = mcp_app

if __name__ == "__main__":
    import os
    import uvicorn
    logging.info("Starting application ...")
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(asgi_app, host="0.0.0.0", port=port)