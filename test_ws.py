import asyncio
import websockets
import json

async def test_websocket():
    """Test WebSocket connection and basic messaging"""
    uri = "ws://localhost:8000/ws/test-room/test-user"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✓ Connected to {uri}")
            
            # Receive join event
            data = await asyncio.wait_for(websocket.recv(), timeout=5)
            msg = json.loads(data)
            print(f"✓ Received: {msg['type']} - {msg['text']}")
            
            # Send a message
            test_msg = {
                "type": "message",
                "user_id": "test-user",
                "room_id": "test-room",
                "text": "Hello, WebSocket!"
            }
            await websocket.send(json.dumps(test_msg))
            print(f"✓ Sent message")
            
            # Receive broadcast
            data = await asyncio.wait_for(websocket.recv(), timeout=5)
            msg = json.loads(data)
            print(f"✓ Received echo: {msg['type']} - {msg['text']}")
            
            print("\n✓ All tests passed!")
            
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
