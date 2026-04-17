from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        await websocket.accept()
        self.active_connections.setdefault(room_id, {})[user_id] = websocket

    def disconnect(self, room_id: str, user_id: str):
        room = self.active_connections.get(room_id, {})
        room.pop(user_id, None)
        if not room:
            self.active_connections.pop(room_id, None)

    async def broadcast_room(self, room_id: str, message: dict, exclude: List[str] = None):
        room = self.active_connections.get(room_id, {})
        stale = []
        for uid, connection in list(room.items()):
            if exclude and uid in exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(uid)
        for uid in stale:
            self.disconnect(room_id, uid)

    def get_users_in_room(self, room_id: str) -> List[str]:
        return list(self.active_connections.get(room_id, {}).keys())