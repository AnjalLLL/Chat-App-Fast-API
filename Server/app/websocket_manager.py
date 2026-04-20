from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.dashboard_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        await websocket.accept()
        self.active_connections.setdefault(room_id, {})[user_id] = websocket

    def disconnect(self, room_id: str, user_id: str):
        room = self.active_connections.get(room_id, {})
        room.pop(user_id, None)
        if not room:
            self.active_connections.pop(room_id, None)

    async def connect_dashboard(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.dashboard_connections[user_id] = websocket

    def disconnect_dashboard(self, user_id: str):
        self.dashboard_connections.pop(user_id, None)

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

    async def send_to_user(self, user_id: str, message: dict):
        print(f"Sending message to user {user_id}, connected users: {list(self.dashboard_connections.keys())}")
        if user_id in self.dashboard_connections:
            try:
                await self.dashboard_connections[user_id].send_json(message)
                print(f"Message sent successfully to {user_id}")
            except Exception as e:
                print(f"Error sending message to {user_id}: {e}")
                self.disconnect_dashboard(user_id)
        else:
            print(f"User {user_id} not connected, message not sent")

    async def broadcast_user_status(self, user_id: str, online: bool):
        status_msg = {
            'type': 'user_status',
            'username': user_id,
            'online': online
        }
        print(f"Broadcasting status for {user_id}: {online}, to {len(self.dashboard_connections)} connections")
        for uid, connection in self.dashboard_connections.items():
            try:
                await connection.send_json(status_msg)
                print(f"Status sent to {uid}")
            except Exception as e:
                print(f"Error sending status to {uid}: {e}")

    def get_users_in_room(self, room_id: str) -> List[str]:
        return list(self.active_connections.get(room_id, {}).keys())

    def get_online_users(self) -> List[str]:
        return list(self.dashboard_connections.keys())