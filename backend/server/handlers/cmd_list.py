'''
    Group: Group 2
    Members:
        - William Lehmann (A1889855)
        - Edward Chipperfield (A1889447)
        - G A Sadman (A1899867)
        - Aditeya Sahu (A1943902)
        
    Description:
        - This module handles the CMD_LIST command, which provides a list of local users.
'''

import json
async def handle_CMD_LIST(ctx, ws, frame):
    # Only local users
    users = list(ctx.local_users.keys())
    await ws.send(json.dumps({
        "type": "USER_LIST",
        "payload": {"users": users}
    }))