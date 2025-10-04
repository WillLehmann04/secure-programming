import uuid
from pathlib import Path

SERVER_ID_FILE = Path("storage/server_id.txt")

class Serverid:
    def __init__(self):
        if SERVER_ID_FILE.exists():
            self.server_id = SERVER_ID_FILE.read_text(encoding="utf-8").strip()
        else:
            self.server_id = str(uuid.uuid4())
            SERVER_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
            SERVER_ID_FILE.write_text(self.server_id, encoding="utf-8")

    def get(self) -> str:
        return self.server_id