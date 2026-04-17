from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import (
    authenticate_user,
    create_token,
    create_user,
    get_last_messages,
    init_db,
    revoke_token,
    verify_token,
)
from .message_router import route_event
from .models import AuthResponse, AuthRequest, ChatEvent, UserCreate
from .websocket_manager import ConnectionManager

app = FastAPI()
manager = ConnectionManager()

# Mount static files from the client directory
static_dir = Path(__file__).parent.parent / "client" / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/")
async def root():
    index_file = static_dir / "index.html"
    return FileResponse(index_file)

@app.post("/register", response_model=AuthResponse)
async def register(user: UserCreate):
    username = user.username.strip().lower()
    if not username or not user.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if not await create_user(username, user.password):
        return AuthResponse(success=False, message="User already exists")
    return AuthResponse(success=True, username=username, token=create_token(username), message="Registered successfully")

@app.post("/login", response_model=AuthResponse)
async def login(user: UserCreate):
    username = user.username.strip().lower()
    if await authenticate_user(username, user.password):
        return AuthResponse(success=True, username=username, token=create_token(username), message="Login successful")
    return AuthResponse(success=False, message="Invalid username or password")

@app.post("/logout", response_model=AuthResponse)
async def logout(request: AuthRequest):
    username = request.username.strip().lower()
    if not request.token or not await verify_token(request.token, username):
        return AuthResponse(success=False, message="Invalid token")
    await revoke_token(request.token)
    return AuthResponse(success=True, username=username, message="Logout successful")

@app.get("/rooms/{room_id}/users")
async def room_users(room_id: str):
    return {"users": manager.get_users_in_room(room_id)}

@app.websocket('/ws/{room_id}/{user_id}')
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_id: str, token: Optional[str] = None):
    username = user_id.strip().lower()
    if not token or not await verify_token(token, username):
        await websocket.close(code=4401)
        return

    await manager.connect(websocket, room_id, username)

    history = await get_last_messages(room_id)
    for message in history:
        await websocket.send_json(message)

    join_event = {
        'type': 'join',
        'user_id': username,
        'room_id': room_id,
        'text': f'{username} joined the room',
        'timestamp': int(datetime.utcnow().timestamp() * 1000),
    }
    await manager.broadcast_room(room_id, join_event)

    try:
        while True:
            data = await websocket.receive_json()
            event = ChatEvent(**data)
            await route_event(manager, event)
    except WebSocketDisconnect:
        manager.disconnect(room_id, username)
        leave_event = {
            'type': 'leave',
            'user_id': username,
            'room_id': room_id,
            'text': f'{username} left the room',
            'timestamp': int(datetime.utcnow().timestamp() * 1000),
        }
        await manager.broadcast_room(room_id, leave_event)
