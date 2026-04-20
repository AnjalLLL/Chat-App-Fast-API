from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .database import (
    authenticate_user,
    create_token,
    create_user,
    get_last_messages,
    init_db,
    revoke_token,
    verify_token,
    get_all_users_list,
    get_private_messages,
    save_private_message,
)
from .message_router import route_event
from .models import AuthResponse, AuthRequest, ChatEvent, UserCreate
from .websocket_manager import ConnectionManager

def get_room_id(user1: str, user2: str) -> str:
    return '_'.join(sorted([user1, user2]))

async def handle_private_message(manager: ConnectionManager, event: ChatEvent):
    print(f"Handling private message: {event}")
    if not event.to_user:
        print("No to_user specified, skipping")
        return

    # Save the private message
    room_id = get_room_id(event.user_id, event.to_user)
    print(f"Saving message to room {room_id}")
    await save_private_message(room_id, event.user_id, event.to_user, event.text, event.timestamp)
    print("Message saved to database")

    # Send to recipient
    private_msg = {
        'type': 'private_message',
        'from': event.user_id.lower(),
        'to': event.to_user.lower(),
        'text': event.text,
        'timestamp': event.timestamp
    }
    print(f"Sending message to recipient {event.to_user.lower()}")
    await manager.send_to_user(event.to_user.lower(), private_msg)

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
    return FileResponse(static_dir / "login.html", media_type="text/html")

@app.get("/login")
async def login_page():
    return FileResponse(static_dir / "login.html", media_type="text/html")

@app.get("/dashboard")
async def dashboard():
    return FileResponse(static_dir / "dashboard.html", media_type="text/html")

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

@app.get("/users")
async def get_all_users():
    return {"users": await get_all_users_list()}

@app.get("/messages/{room_id}")
async def get_private_messages(room_id: str):
    return {"messages": await get_private_messages(room_id)}
@app.get("/private-messages/{room_id}")
async def get_private_messages_api(room_id: str):
    messages = await get_private_messages(room_id)
    return {"messages": messages}
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
@app.websocket('/ws/dashboard/{user_id}')
async def dashboard_websocket(websocket: WebSocket, user_id: str, token: Optional[str] = None):
    username = user_id.strip().lower()
    if not token or not await verify_token(token, username):
        await websocket.close(code=4401)
        return

    await manager.connect_dashboard(websocket, username)

    # Send list of currently online users to the new user
    online_users_list = manager.get_online_users()
    for user in online_users_list:
        if user != username:  # Don't send self as online
            await websocket.send_json({
                'type': 'user_status',
                'username': user,
                'online': True
            })

    # Broadcast new user's online status to all others
    await manager.broadcast_user_status(username, True)

    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received WebSocket message from {username}: {data}")
            
            if data.get('type') == 'private_message':
                print(f"Processing private message: {data}")
                # Handle private message
                event = ChatEvent(
                    type='private_message',
                    user_id=data.get('user_id'),
                    room_id=data.get('room_id'),
                    text=data.get('text'),
                    to_user=data.get('to_user'),
                    timestamp=data.get('timestamp', int(datetime.utcnow().timestamp() * 1000))
                )
                print(f"Created event: {event}")
                await handle_private_message(manager, event)
                print("Message handled successfully")
            elif data.get('type') == 'typing':
                # Handle typing indicator for private chat
                await manager.send_to_user(data.get('to_user'), data)
    except WebSocketDisconnect:
        manager.disconnect_dashboard(username)
        await manager.broadcast_user_status(username, False)
    except Exception as e:
        print(f"Error in dashboard websocket: {e}")
        manager.disconnect_dashboard(username)