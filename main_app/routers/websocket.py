from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from typing import Dict, List
import json
import asyncio
from uuid import UUID
from datetime import datetime, timezone
import logging
import jwt
from ..auth import SECRET_KEY, ALGORITHM

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}
        self.user_status: Dict[str, str] = {}
        self.typing_status: Dict[str, Dict[str, bool]] = {}
        self.connection_heartbeat: Dict[str, datetime] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        connection_id = f"{user_id}_{datetime.now().timestamp()}"
        
        self.active_connections[connection_id] = websocket
        self.connection_heartbeat[connection_id] = datetime.now(timezone.utc)
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(connection_id)
        
        self.user_status[user_id] = "online"
        return connection_id

    def disconnect(self, connection_id: str, user_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if connection_id in self.connection_heartbeat:
            del self.connection_heartbeat[connection_id]
        
        if user_id in self.user_connections:
            self.user_connections[user_id] = [
                conn for conn in self.user_connections[user_id] 
                if conn != connection_id
            ]
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                self.user_status[user_id] = "offline"
    
    def update_heartbeat(self, connection_id: str):
        """Update heartbeat timestamp for connection"""
        if connection_id in self.connection_heartbeat:
            self.connection_heartbeat[connection_id] = datetime.now(timezone.utc)

    async def broadcast_typing(self, booking_id: str, user_id: str, is_typing: bool, other_user_id: str):
        if booking_id not in self.typing_status:
            self.typing_status[booking_id] = {}
        
        self.typing_status[booking_id][user_id] = is_typing
        
        await self.send_to_user(other_user_id, {
            "type": "typing_status",
            "booking_id": booking_id,
            "user_id": user_id,
            "is_typing": is_typing
        })

    def get_user_status(self, user_id: str) -> str:
        return self.user_status.get(user_id, "offline")

    async def send_to_user(self, user_id: str, message: dict):
        """Send message to all connections of a user"""
        if user_id in self.user_connections:
            disconnected = []
            for connection_id in self.user_connections[user_id]:
                if connection_id in self.active_connections:
                    try:
                        await self.active_connections[connection_id].send_text(
                            json.dumps(message, default=str)
                        )
                    except:
                        disconnected.append(connection_id)
            
            for conn_id in disconnected:
                self.disconnect(conn_id, user_id)

manager = ConnectionManager()

def verify_websocket_token(token: str) -> dict:
    """Verify JWT token for WebSocket connection"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise Exception("Invalid token payload")
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Token expired")
    except jwt.JWTError:
        raise Exception("Invalid token")
    except Exception as e:
        raise Exception(str(e))

@router.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket, 
    token: str = Query(...)
):
    """WebSocket endpoint for real-time messaging"""
    connection_id = None
    try:
        # Verify token before accepting connection
        try:
            payload = verify_websocket_token(token)
            user_id = payload["sub"]
        except Exception as e:
            await websocket.close(code=4001, reason=str(e))
            return
        
        connection_id = await manager.connect(websocket, user_id)
        
        await websocket.send_text(json.dumps({
            "type": "connected",
            "user_id": user_id,
            "status": "online",
            "connection_id": connection_id
        }))
        
        # Start heartbeat
        asyncio.create_task(heartbeat_task(websocket, connection_id, user_id))
        
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type")
            
            if message_type == "ping":
                manager.update_heartbeat(connection_id)
                await websocket.send_text(json.dumps({"type": "pong"}))
            
            elif message_type == "typing":
                booking_id = message_data.get("booking_id")
                is_typing = message_data.get("is_typing", False)
                other_user_id = message_data.get("other_user_id")
                
                if booking_id and other_user_id:
                    await manager.broadcast_typing(booking_id, user_id, is_typing, other_user_id)
            
            elif message_type == "get_status":
                target_user_id = message_data.get("target_user_id")
                if target_user_id:
                    status = manager.get_user_status(target_user_id)
                    await websocket.send_text(json.dumps({
                        "type": "user_status",
                        "user_id": target_user_id,
                        "status": status
                    }))
    
    except WebSocketDisconnect:
        if connection_id:
            manager.disconnect(connection_id, user_id)
    except Exception as e:
        if connection_id:
            manager.disconnect(connection_id, user_id)

async def heartbeat_task(websocket: WebSocket, connection_id: str, user_id: str):
    """Send periodic heartbeat to maintain connection"""
    try:
        while connection_id in manager.active_connections:
            await asyncio.sleep(30)  # Send ping every 30 seconds
            if connection_id in manager.active_connections:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except:
        manager.disconnect(connection_id, user_id)

# Global functions for real-time notifications
async def notify_new_message(recipient_user_id: str, sender_name: str, message_data: dict):
    """Send real-time notification when new message arrives"""
    notification = {
        "type": "new_message",
        "sender_name": sender_name,
        "data": message_data
    }
    await manager.send_to_user(recipient_user_id, notification)

async def notify_message_read(sender_user_id: str, message_ids: list):
    """Notify sender when messages are read"""
    notification = {
        "type": "messages_read",
        "message_ids": message_ids
    }
    await manager.send_to_user(sender_user_id, notification)