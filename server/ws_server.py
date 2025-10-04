from __future__ import annotations
import asyncio, websockets
from server.bootstrap import init_persistence
from server.router import handle_connection

async def main():
    init_persistence()
    async with websockets.serve(handle_connection, "0.0.0.0", 8765, max_size=2**20):
        print("WS server on :8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
