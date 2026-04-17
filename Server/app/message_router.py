from .database import save_message
from .models import ChatEvent
from .websocket_manager import ConnectionManager


async def route_event(manager: ConnectionManager, event: ChatEvent):
    if event.type == 'message':
        await save_message(event.room_id, event.user_id, event.type.value, event.text, event.timestamp)
        await manager.broadcast_room(event.room_id, event.dict())
    elif event.type == 'typing':
        await manager.broadcast_room(event.room_id, event.dict(), exclude=[event.user_id])
    elif event.type in {'join', 'leave', 'presence'}:
        await manager.broadcast_room(event.room_id, event.dict())
    else:
        await manager.broadcast_room(
            event.room_id,
            {
                'type': 'error',
                'user_id': event.user_id,
                'room_id': event.room_id,
                'text': f'Unsupported event type: {event.type}',
                'timestamp': event.timestamp,
            },
        )
