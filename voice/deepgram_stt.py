import os
from dotenv import load_dotenv
from deepgram import DeepgramClient
from deepgram.core.events import EventType

load_dotenv()


class DeepgramSTT:
    """Handles real-time streaming audio transcription using Deepgram API v7.6.0."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY must be configured in environment.")
        self.client = DeepgramClient(api_key=self.api_key)

    def transcribe_blob(self, file_bytes: bytes, mime_type: str = "audio/wav") -> str:
        """Transcribes pre-recorded audio bytes to text using Deepgram SDK v7.6.0."""
        try:
            response = self.client.listen.v1.media.transcribe_file(
                request=file_bytes,
                model="nova-2-general",
                smart_format=True,
            )
            if hasattr(response, "results") and response.results and response.results.channels:
                alt = response.results.channels[0].alternatives[0]
                return alt.transcript
            return ""
        except Exception as e:
            print(f"Deepgram STT Blob Error: {e}")
            return ""

    def create_live_stream(
        self,
        model: str = "nova-2-general",
        encoding: str = "linear16",
        sample_rate: int = 16000,
        **kwargs,
    ):
        """
        Establishes a real-time WebSocket live transcription stream using Deepgram SDK v7.6.0.

        Returns the WebSocket connection context manager (v2 streaming API).
        Usage:
            with stt.create_live_stream() as connection:
                connection.on(EventType.MESSAGE, on_message)
                connection.on(EventType.OPEN, on_open)
                connection.start_listening()
                connection.send_media(audio_chunk)
        """
        try:
            connection = self.client.listen.v2.connect(
                model=model,
                encoding=encoding,
                sample_rate=sample_rate,
                **kwargs,
            )
            return connection
        except Exception as e:
            print(f"Deepgram Live STT Connection Error: {e}")
            raise e
