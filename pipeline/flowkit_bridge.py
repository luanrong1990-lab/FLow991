"""
FlowKit WebSocket bridge server for controlling Google Flow extension.
"""
import asyncio
import json
import base64
from typing import Dict, Any, Optional, Callable
import websockets
from pathlib import Path


class FlowKitBridge:
    """WebSocket bridge between Python and Chrome extension."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.pending_jobs: Dict[str, asyncio.Future] = {}
        self.server = None
        self.running = False
    
    async def start(self):
        """Start the WebSocket server."""
        self.server = await websockets.serve(
            self.handler,
            self.host,
            self.port
        )
        self.running = True
        print(f"FlowKit bridge started on ws://{self.host}:{self.port}")
    
    async def stop(self):
        """Stop the WebSocket server."""
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
    
    async def handler(self, websocket):
        """Handle WebSocket connections from extension."""
        self.clients.add(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "poll":
                    # Extension is polling - could send job if available
                    pass
                elif msg_type == "result":
                    # Extension returned image result
                    job_id = data.get("job_id")
                    images = data.get("images", [])
                    
                    if job_id in self.pending_jobs:
                        self.pending_jobs[job_id].set_result(images)
                        del self.pending_jobs[job_id]
        finally:
            self.clients.discard(websocket)
    
    async def send_job(
        self,
        prompt: str,
        ref_base64: Optional[str] = None,
        n: int = 1,
        timeout: float = 180.0
    ) -> list:
        """
        Send an image generation job to the extension.
        
        Args:
            prompt: Image generation prompt
            ref_base64: Reference sheet as base64 PNG (optional)
            n: Number of images to generate
            timeout: Timeout in seconds
        
        Returns:
            List of base64-encoded images
        
        Raises:
            TimeoutError: If no response within timeout
            RuntimeError: If no extension connected
        """
        if not self.clients:
            raise RuntimeError(
                "No Chrome extension connected. Please open Google Flow tab and ensure extension is running."
            )
        
        job_id = f"job_{len(self.pending_jobs) + 1}"
        future = asyncio.Future()
        self.pending_jobs[job_id] = future
        
        # Broadcast job to all clients (extension will pick it up)
        job_msg = {
            "type": "job",
            "job_id": job_id,
            "prompt": prompt,
            "ref": ref_base64,
            "n": n
        }
        
        await asyncio.gather(
            *[client.send(json.dumps(job_msg)) for client in self.clients],
            return_exceptions=True
        )
        
        # Wait for result
        try:
            images = await asyncio.wait_for(future, timeout=timeout)
            return images
        except asyncio.TimeoutError:
            del self.pending_jobs[job_id]
            raise TimeoutError(
                f"Image generation timed out after {timeout}s. "
                "Please check if Google Flow tab is open and responsive."
            )


# Global bridge instance
_bridge: Optional[FlowKitBridge] = None


def get_bridge() -> FlowKitBridge:
    """Get or create the global bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = FlowKitBridge()
    return _bridge


async def start_bridge_background():
    """Start bridge server in background task."""
    bridge = get_bridge()
    await bridge.start()


def load_mascot_ref() -> str:
    """Load mascot reference sheet as base64."""
    ref_path = Path(__file__).parent.parent / "assets" / "mascot_ref.png"
    if not ref_path.exists():
        raise FileNotFoundError(
            f"Mascot reference sheet not found at {ref_path}. "
            "Please create it using the prompt in spec §2.1"
        )
    
    with open(ref_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
