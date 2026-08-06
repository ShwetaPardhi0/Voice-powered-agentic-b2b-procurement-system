import io
import asyncio
from typing import AsyncGenerator


class AudioStream:
    """
    Manages audio data buffering and chunk iteration for real-time voice pipelines.
    Supports both synchronous byte blobs and async live streams.
    """

    def __init__(self, chunk_size: int = 4096):
        self.chunk_size = chunk_size
        self._buffer = io.BytesIO()

    def write(self, data: bytes) -> None:
        """Append raw audio bytes to internal buffer."""
        self._buffer.write(data)

    def read_all(self) -> bytes:
        """Return full buffered content."""
        self._buffer.seek(0)
        return self._buffer.read()

    def reset(self) -> None:
        """Clear the buffer."""
        self._buffer = io.BytesIO()

    def iter_chunks(self) -> list[bytes]:
        """
        Return buffer contents as a list of fixed-size byte chunks.
        Useful for feeding to Deepgram live streaming endpoints.
        """
        self._buffer.seek(0)
        chunks = []
        while True:
            chunk = self._buffer.read(self.chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
        return chunks

    async def stream_chunks(self) -> AsyncGenerator[bytes, None]:
        """
        Async generator to yield chunks from the buffer.
        Simulates a real-time stream from a preloaded file for testing.
        """
        self._buffer.seek(0)
        while True:
            chunk = self._buffer.read(self.chunk_size)
            if not chunk:
                break
            yield chunk
            await asyncio.sleep(0)  # yield control to the event loop
