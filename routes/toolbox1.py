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
    import cv2
    import numpy as np
    import io
    from PIL import Image

    # Decode the base64 string into image bytes
    decoded_bytes = base64.b64decode(base64_encoded_str)
    image = Image.open(io.BytesIO(decoded_bytes)).convert("RGB")

    # Convert the PIL image to a NumPy array for OpenCV processing
    image_np = np.array(image)

    # Convert the image to grayscale
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

    # Apply edge detection
    edges = cv2.Canny(gray, 50, 150)

    # Find contours in the image
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        # Approximate the contour to a polygon
        epsilon = 0.04 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # Determine the shape based on the number of vertices
        vertices = len(approx)
        if vertices == 3:
            return "triangle"
        elif vertices == 4:
            # Check if the shape is a square or rectangle
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = w / float(h)
            if 0.95 <= aspect_ratio <= 1.05:
                return "square"
            else:
                return "rectangle"
        elif vertices > 4:
            return "circle"

    return "unknown"
