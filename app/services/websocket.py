import json
from typing import List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        print(f"Broadcasting to {len(self.active_connections)} connections: {message[:100]}...")
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to a connection: {e}")
                pass

manager = ConnectionManager()

async def broadcast_usage():
    from app.services import db
    stats = await db.get_total_usage()
    await manager.broadcast(json.dumps({
        "type": "usage_update",
        "stats": stats
    }))

async def broadcast_status():
    from app.services import db
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(db.select(db.Lecture).order_by(db.Lecture.created_at.desc()))
        lectures = result.scalars().all()
        lecture_list = []
        for l in lectures:
            lecture_list.append({
                "id": l.id, "title": l.title, "status": l.status,
                "progress": l.progress, "current_step": l.current_step,
                "active_model": l.active_model, "created_at": str(l.created_at)
            })
        await manager.broadcast(json.dumps({
            "type": "status_update",
            "lectures": lecture_list
        }))
