import json
import logging

from flask import request, Blueprint
from fastmcp import FastMCP
from routes import app

logger = logging.getLogger(__name__)
mcp = FastMCP("toolbox1")

toolbox1_bp = Blueprint('toolbox1', __name__)

@mcp.tool
def name() -> str:
    """Return the name of the toolbox."""
    return "Toolbox 1"

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@mcp.tool
def subtract(a: int, b: int) -> int:
    """Subtract b from a."""
    return a - b

@mcp.tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

@mcp.tool
def divide(a: int, b: int) -> int:
    """Divide a by b."""
    return a / b

@mcp.tool
def base64_decoder_shape(base64_encoded_str: str) -> str:
    """Decode a base64 encoded string of an image and return the shape (rectangle, triangle, or circle)."""
    import base64
    from PIL import Image
    import io

    # Decode the base64 string into image bytes
    decoded_bytes = base64.b64decode(base64_encoded_str)
    image = Image.open(io.BytesIO(decoded_bytes))

    # Analyze the image dimensions to determine the shape
    width, height = image.size
    if width == height:
        return "circle"
    elif width > height:
        return "rectangle"
    else:
        return "triangle"