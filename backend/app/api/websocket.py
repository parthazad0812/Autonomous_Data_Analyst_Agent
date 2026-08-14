"""
WebSocket Manager + FastAPI WebSocket endpoint.

Architecture:
  1. Client connects to ws://localhost:8000/ws/analysis/{session_id}
  2. Redis pub/sub subscribes to channel "analysis:{session_id}" (if Redis available)
  3. Analysis service publishes events to that channel
  4. WS handler forwards events to the browser in real-time
  5. Falls back to in-memory broadcast when Redis is unavailable
"""

import json
import asyncio
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages active WebSocket connections per session."""

    def __init__(self) -> None:
        # session_id -> set of active WebSocket connections
        self._active: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self._active.setdefault(session_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        sockets = self._active.get(session_id, set())
        sockets.discard(websocket)
        if not sockets:
            self._active.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict) -> None:
        """Send a message to all clients watching this session."""
        sockets = list(self._active.get(session_id, set()))
        dead = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, session_id)


# Singleton manager
manager = ConnectionManager()


def _redis_available() -> bool:
    """Check if Redis is reachable (non-blocking, cached-ish check)."""
    try:
        import redis as sync_redis
        r = sync_redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


@router.websocket("/ws/analysis/{session_id}")
async def analysis_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint. Subscribes to Redis pub/sub channel
    'analysis:{session_id}' and forwards all events to the client.
    Falls back to in-memory broadcast if Redis is unavailable.
    """
    await manager.connect(websocket, session_id)

    # Send immediate confirmation
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "message": "Connected to analysis stream",
    })

    redis = None
    pubsub = None
    use_redis = False

    try:
        # Try to connect to Redis for pub/sub
        try:
            from redis.asyncio import Redis as AsyncRedis
            redis = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
            await redis.ping()
            pubsub = redis.pubsub()
            channel = f"analysis:{session_id}"
            await pubsub.subscribe(channel)
            use_redis = True
        except Exception as e:
            logger.warning(f"Redis unavailable for WebSocket pub/sub: {e}. Using in-memory fallback.")
            use_redis = False

        if use_redis and pubsub:
            # Listen for Redis messages and forward to client
            async def redis_listener():
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await manager.broadcast(session_id, data)
                        except (json.JSONDecodeError, Exception):
                            pass

            # Also handle client disconnects
            async def ws_listener():
                try:
                    while True:
                        msg = await websocket.receive_text()
                except WebSocketDisconnect:
                    pass

            await asyncio.gather(
                redis_listener(),
                ws_listener(),
                return_exceptions=True,
            )
        else:
            # In-memory fallback: just keep the connection alive
            # Events will be pushed via manager.broadcast() directly
            try:
                while True:
                    msg = await websocket.receive_text()
            except WebSocketDisconnect:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(f"analysis:{session_id}")
                await pubsub.aclose()
            except Exception:
                pass
        if redis:
            try:
                await redis.aclose()
            except Exception:
                pass
        manager.disconnect(websocket, session_id)


async def publish_event(session_id: str, event: dict) -> None:
    """
    Publish an event to the Redis channel for this session.
    Falls back to in-memory broadcast if Redis is unavailable.
    """
    try:
        from redis.asyncio import Redis as AsyncRedis
        redis = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
        try:
            await redis.publish(f"analysis:{session_id}", json.dumps(event))
        finally:
            await redis.aclose()
    except Exception:
        # Fallback: broadcast directly via manager (works for single-process deployments)
        await manager.broadcast(session_id, event)


def publish_event_sync(session_id: str, event: dict) -> None:
    """Synchronous wrapper for publishing events from non-async code."""
    try:
        import redis as sync_redis
        r = sync_redis.from_url(settings.redis_url, decode_responses=True)
        try:
            r.publish(f"analysis:{session_id}", json.dumps(event))
        finally:
            r.close()
    except Exception:
        # If Redis is unavailable, try in-memory broadcast via asyncio event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(manager.broadcast(session_id, event))
            else:
                loop.run_until_complete(manager.broadcast(session_id, event))
        except Exception:
            # Last resort: log and continue — don't crash the analysis pipeline
            logger.warning(
                f"Could not publish WebSocket event for session {session_id}: Redis unavailable and no event loop"
            )
