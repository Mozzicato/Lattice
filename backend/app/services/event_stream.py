"""
Event streaming manager for real-time job progress updates.
Uses asyncio queues to stream updates from background tasks to client connections.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class EventStreamManager:
    """Manages event streams for job progress updates."""
    
    def __init__(self):
        self.streams: dict[int, asyncio.Queue] = {}
    
    def create_stream(self, job_id: int) -> None:
        """Create a new event stream for a job."""
        if job_id not in self.streams:
            self.streams[job_id] = asyncio.Queue()
            logger.debug(f"Created event stream for job {job_id}")
    
    async def publish_event(self, job_id: int, event_type: str, data: dict) -> None:
        """Publish an event to a job's stream."""
        if job_id not in self.streams:
            self.create_stream(job_id)
        
        event = {
            "type": event_type,
            "data": data
        }
        try:
            await self.streams[job_id].put(event)
        except Exception as e:
            logger.error(f"Failed to publish event to job {job_id}: {e}")
    
    async def stream_events(self, job_id: int, timeout: int = 300) -> AsyncGenerator[str, None]:
        """Stream events for a job as Server-Sent Events format.
        
        Args:
            job_id: The job ID to stream events for
            timeout: Maximum time to keep stream open (seconds)
        """
        if job_id not in self.streams:
            self.create_stream(job_id)
        
        queue = self.streams[job_id]
        
        try:
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    
                    # Format as SSE
                    sse_data = f"data: {json.dumps(event)}\n\n"
                    yield sse_data
                    
                    # If job is done, close the stream
                    if event.get("type") == "complete" or event.get("type") == "error":
                        break
                        
                except asyncio.TimeoutError:
                    # Send a keep-alive comment
                    yield ": keep-alive\n\n"
                    
        except Exception as e:
            logger.error(f"Error streaming events for job {job_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
        finally:
            # Clean up the stream
            if job_id in self.streams:
                del self.streams[job_id]
                logger.debug(f"Cleaned up event stream for job {job_id}")


# Global instance
event_manager = EventStreamManager()
