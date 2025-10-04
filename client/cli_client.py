from __future__ import annotations
import asyncio, json, os, sys
import websockets

from .config import load_client_keys_from_config
from .rpc import listener
from .commands import cmd_list, cmd_tell, cmd_all, cmd_file, get_public_group_key  # get_public_group_key

WS_URL = os.environ.get("SOCP_WS", "ws://localhost:8765")

def now_ts() -> str:
    import time; return str(int(time.time()))

def build_user_hello(user_id: str, pubkey_pem: str) -> dict:
    return {"type": "USER_HELLO", "payload": {"user_id": user_id, "pubkey": pubkey_pem}, "ts": now_ts()}

async def main_loop(cfg_path: str):
    user_id, privkey_pem, pubkey_pem = load_client_keys_from_config(cfg_path)
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps(build_user_hello(user_id, pubkey_pem)))
        print("sent USER_HELLO; awaiting server responses...")

        try:
            await get_public_group_key(ws, user_id, privkey_pem)
            print("[init] public group key unwrapped & cached")
        except Exception as e:
            print(f"[init] warning: couldn't unwrap public group key: {e}")

        task = asyncio.create_task(listener(ws))
        print("Enter: /list | /tell <user> <text> | /all <text> | /file <user|public> <path>")
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line == "/list":
                await cmd_list(ws, user_id)
            elif line.startswith("/tell "):
                _, to, text = line.split(" ", 2)
                await cmd_tell(ws, user_id, privkey_pem, to, text)
            elif line.startswith("/all "):
                await cmd_all(ws, user_id, privkey_pem, line[len("/all "):])
            elif line.startswith("/file "):
                _, target, path = line.split(" ", 2)
                await cmd_file(ws, user_id, privkey_pem, target, path)
            elif line in ("/quit", "/exit"):
                break
            else:
                print("unknown command")
        task.cancel()
        await ws.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m client.cli_client client/<user>.json")
        sys.exit(1)
    asyncio.run(main_loop(sys.argv[1]))
