import json
async def handle_CMD_LIST(ctx, ws, frame):
    # Only local users
    users = list(ctx.local_users.keys())
    await ws.send(json.dumps({
        "type": "USER_LIST",
        "payload": {"users": users}
    }))