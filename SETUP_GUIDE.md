# Chat Application - Complete Setup Guide

## Features Implemented

### 1. **Login/Register Portal**
- Beautiful gradient UI with modern design
- New user registration with password security
- Existing user login
- Form validation
- Error and success messages
- Auto-redirect to dashboard after successful authentication

### 2. **Dashboard with Private Messaging**
- **Left Sidebar**: 
  - List of all registered users
  - Online/Offline status indicators (green for online, gray for offline)
  - Click any user to start a private conversation
  - Active user highlight

- **Chat Area**:
  - Shows selected user at the top with their online status
  - Message history with timestamps
  - Different message styling for sent (blue, right-aligned) vs received (gray, left-aligned)
  - Real-time message display
  - User identification for each message

- **Message Input**:
  - Multi-line text input with auto-height adjustment
  - Send button (disabled when no recipient selected)
  - Enter to send (Shift+Enter for new line)

## Architecture

### Backend (FastAPI)
```
Server/app/
├── main.py              # FastAPI routes and WebSocket endpoints
├── database.py          # Database operations and schema
├── websocket_manager.py # WebSocket connection management
├── message_router.py    # Event routing logic
└── models.py           # Pydantic models
```

### Frontend (HTML/JavaScript)
```
Server/client/static/
├── login.html          # Login/Register page
└── dashboard.html      # Main chat dashboard
```

## API Endpoints

### Authentication
- `POST /register` - Register new user
- `POST /login` - Login user
- `POST /logout` - Logout user
- `GET /users` - Get all registered users

### Messages
- `GET /messages/{room_id}` - Get private message history between two users
- `WebSocket /ws/dashboard/{user_id}` - Real-time dashboard connection for private messages

### Room-based Chat (Optional - original implementation)
- `GET /rooms/{room_id}/users` - Get users in a room
- `WebSocket /ws/{room_id}/{user_id}` - Room-based chat WebSocket

## How to Use

### 1. Start the Server
```bash
python -m uvicorn Server.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Access the Application
- Open browser: `http://localhost:8000`
- You'll see the login/register portal

### 3. Create Account or Login
- **To Register**: 
  - Click "Register here" link
  - Enter username and password
  - Click "Register"

- **To Login**:
  - Enter username and password
  - Click "Login"

### 4. Use Dashboard
- After login, you'll see the dashboard
- Left sidebar shows all other users
- Click any user to open private chat
- Green dot = Online, Gray dot = Offline
- Type message and press Enter to send
- See message history with timestamps

### 5. Multiple Users
- Open multiple browser tabs/windows
- Register/login different users
- See real-time user status updates
- Send messages between users

## Database Schema

### Users Table
- `id` (Integer, Primary Key)
- `username` (String, Unique)
- `password_hash` (String)
- `created_at` (DateTime)

### Messages Table
- `id` (Integer, Primary Key)
- `room_id` (String, Indexed) - Format: "user1_user2" (sorted)
- `user_id` (String) - Sender
- `event_type` (String) - "private_message"
- `content` (Text) - Format: "recipient:message_text"
- `timestamp` (Integer, Indexed)

### Revoked Tokens Table
- `id` (Integer, Primary Key)
- `token` (Text, Unique) - Logout tokens
- `revoked_at` (DateTime)

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy, asyncpg, Alembic
- **Frontend**: HTML5, CSS3, Vanilla JavaScript, WebSockets
- **Database**: PostgreSQL (async with asyncpg)
- **Authentication**: Token-based (HMAC-SHA256)

## Features in Detail

### User Authentication
- Password hashing with PBKDF2-HMAC-SHA256
- 16-byte salt per password
- 200,000 iterations for security
- Token-based authentication with expiration
- Token revocation on logout

### Real-time Updates
- WebSocket connections for instant messaging
- Automatic online/offline status broadcasting
- Connection management and cleanup
- Graceful disconnect handling

### Private Messaging
- One-to-one chat between users
- Message persistence in database
- Chat history loaded on conversation select
- Room ID derived from sorted usernames for consistency

## Troubleshooting

### Server won't start
1. Ensure all dependencies installed: `pip install -r requirements.txt`
2. Check PostgreSQL connection string in `.env`
3. Run migrations: `alembic upgrade head`

### Messages not updating in real-time
1. Check WebSocket connection in browser console
2. Verify both users connected to dashboard WebSocket
3. Clear browser cache and refresh

### Database errors
1. Verify PostgreSQL is running
2. Check DATABASE_URL environment variable
3. Run alembic migrations: `alembic upgrade head`

## Notes

- Users are case-insensitive (converted to lowercase)
- Message room IDs are sorted to ensure consistency
- Token expiration: 24 hours by default
- Private messages are stored per room, not per user
- Only connected users receive real-time status updates
