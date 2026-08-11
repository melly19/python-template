from flask import Flask
from routes.toolbox1 import mcp

app = Flask(__name__)

mcp_app = mcp.http_app(path="/mcp")

app.mount("/mcp", mcp_app)