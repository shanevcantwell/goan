# api/sse_manager.py
import asyncio
import logging
import json
from typing import List

logger = logging.getLogger(__name__)

class SSEManager:
    """
    A singleton manager for broadcasting Server-Sent Events to all connected clients.
    This replaces the direct-to-UI queue with a pub/sub model.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SSEManager, cls).__new__(cls)
            cls._instance.clients: List[asyncio.Queue] = []
            cls._instance.lock = asyncio.Lock()
        return cls._instance

    async def connect(self, client_queue: asyncio.Queue):
        """Registers a new client queue to receive broadcasts."""
        async with self.lock:
            self.clients.append(client_queue)
        logger.info(f"SSE client connected. Total clients: {len(self.clients)}")

    async def disconnect(self, client_queue: asyncio.Queue):
        """Removes a client queue."""
        async with self.lock:
            try:
                self.clients.remove(client_queue)
            except ValueError:
                pass # Client may have already been removed
        logger.info(f"SSE client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, flag: str, data: dict):
        """Broadcasts a message to all connected clients."""
        message = json.dumps({"event": flag, "data": data})
        async with self.lock:
            for q in self.clients:
                await q.put(message)

# Singleton instance
sse_manager = SSEManager()
