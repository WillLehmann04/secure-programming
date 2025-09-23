# server/main.py
from __future__ import annotations

# 1) Must be first: make sure persistence is initialised
from server.bootstrap import init_persistence
init_persistence()

# 2) Then import the rest of your server stack so they can safely call the façade
# e.g. transport, routing, handlers, etc.
# from transport.websocket_server import run_ws_server
# ...

if __name__ == "__main__":
    # run_ws_server(...)
    pass

