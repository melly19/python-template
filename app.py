import logging

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

# FastMCP speaks ASGI and Flask speaks WSGI, so the two are joined the other way
# round from a blueprint: an ASGI entrypoint hands /mcp to FastMCP and wraps the
# Flask app for everything else. `mcp_app` already serves its own /mcp path, so
# it is dispatched to unstripped and no redirect is involved.
mcp_app = mcp.http_app(path="/mcp")
flask_asgi_app = WSGIMiddleware(app)


async def asgi_app(scope, receive, send):
    if scope["type"] == "lifespan":
        # FastMCP's session manager is started here; Flask needs no lifespan.
        await mcp_app(scope, receive, send)
        return
    path = scope.get("path", "")
    if path == "/mcp" or path.startswith("/mcp/"):
        await mcp_app(scope, receive, send)
        return
    await flask_asgi_app(scope, receive, send)


if __name__ == "__main__":
    import os
    import uvicorn
    logging.info("Starting application ...")
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(asgi_app, host="0.0.0.0", port=port)
