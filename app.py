import logging

from starlette.applications import Starlette
from starlette.routing import Mount
from a2wsgi import WSGIMiddleware
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

mcp_app = mcp.http_app(path="/")
asgi_app = Starlette(
    routes=[
        Mount("/mcp", app=mcp_app),
        Mount("/", app=WSGIMiddleware(app)),
    ],
    lifespan=mcp_app.lifespan
)

if __name__ == "__main__":
    import os
    import uvicorn
    logging.info("Starting application ...")
    uvicorn.run(asgi_app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
