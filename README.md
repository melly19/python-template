# python-template

These instruction are to help you solve a test challenge "Calculate Square".

## Calculate Square

### Instructions

This challenge requires you to return the squared of two numbers given an itput.

### Endpoint
Create an endpoint `/square` that accepts a JSON payload over `POST` described below.

### Input

Example:
`{ "input": 5 }`

### Output

Example: 
`25`

## Explanation

This project is built using [flask](https://flask.palletsprojects.com/en/2.3.x/) and is meant to run a REST server which we will be using mainly for UBS Coding Challenge.

By default, `app.py` contains a root path `/` which would return a default string value. And the implementation within `routes/square.py` exposes a route `/square` accepting a `POST` request with the given input to return a number as an output.

To extend this template further, add more endpoints in the `routes` directory and import the functions within `routes/__init__.py`. This method will be the entry point when you submit your solution for evaluation.

Note the init.py file in each folder. This file makes python treat directories containing it to be loaded in a module

Also note that when using render as cloud PAAS, you should be adding `gunicorn -k uvicorn.workers.UvicornWorker app:asgi_app` as the start command.

## MCP server

The FastMCP server in `routes/toolbox1.py` is served at `/mcp`. Because FastMCP is
ASGI and Flask is WSGI, `app.py` exposes `asgi_app` as the real entrypoint: it routes
`/mcp` to FastMCP and everything else to the Flask app. `app` is still the plain Flask
app, so blueprints and `@app.route` are unchanged — but it must be served through
`asgi_app` under an ASGI worker, since FastMCP's session manager only starts if the
ASGI lifespan runs. Plain `gunicorn app:app` would serve the Flask routes but not `/mcp`.