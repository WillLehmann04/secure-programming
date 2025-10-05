import asyncio
import json
import sys
import websockets

from client.commands_all import cmd_all

from .constants import WS_URL
from .config import load_client_cfg
from .envelopes import user_hello, user_advertise, user_remove
from .transport import Transport
from .commands import cmd_list, cmd_tell, cmd_channel


async def main_loop(cfg_path: str):
    user_id, privkey_pem, pubkey_pem, server_id, privkey_store, pake_password, meta, version = load_client_cfg(cfg_path)

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps(user_hello(server_id, user_id, pubkey_pem, privkey_pem)))
        print("sent USER_HELLO; awaiting server responses...")

        await ws.send(json.dumps(user_advertise(user_id, pubkey_pem, privkey_store, pake_password, meta, version, privkey_pem)))
        print("sent USER_ADVERTISE")

        transport = Transport(ws)
        listener_task = asyncio.create_task(transport.listener(privkey_pem))

        print("Enter commands: /list, /tell <user> <text>, /all <text>, /quit")
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line == "/list":
                await cmd_list(ws, user_id, server_id)
            elif line.startswith("/tell "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    print("usage: /tell <user> <text>")
                    continue
                to, text = parts[1], parts[2]
                await cmd_tell(ws, user_id, privkey_pem, to, text, transport.tables)
            elif line.startswith("/all "):
                text = line[len("/all "):]
                await cmd_all(ws, user_id, privkey_pem, text, transport.tables)
            elif line == "/quit":
                await ws.send(json.dumps(user_remove(user_id, privkey_pem)))
                await ws.close()
                break
            else:
                print("unknown command", line)


                listener_task.cancel()
                await ws.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m client.main <client_config.json>")
        sys.exit(1)
    asyncio.run(main_loop(sys.argv[1]))
