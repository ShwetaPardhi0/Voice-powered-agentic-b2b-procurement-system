import os
from dotenv import load_dotenv
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    LiveOptions,
    LiveTranscriptionEvents
)

load_dotenv()

class DeepgramSTT:
    """Handles audio transcription logic using Deepgram API."""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY must be configured in environment.")
        self.client = DeepgramClient(self.api_key)

    def transcribe_blob(self, file_bytes: bytes, mime_type: str = "audio/wav") -> str:
        """Transcribes pre-recorded audio bytes to text."""
        try:
            payload = {
                "buffer": file_bytes,
            }
            options = PrerecordedOptions(
                model="nova-2-general",
                smart_format=True,
                mimetype=mime_type
            )
            response = self.client.listen.prerecorded.v("1").transcribe_file(payload, options)
            transcript = response.results.channels[0].alternatives[0].transcript
            return transcript
        except Exception as e:
            print(f"Deepgram Pre-recorded STT Error: {e}")
            raise e

    def create_live_stream(self, options: LiveOptions = None):
        """
        Creates a real-time live transcribing stream client.
        Caller is expected to register events on the returned connection.
        """
        try:
            if not options:
                options = LiveOptions(
                    model="nova-2-general",
                    language="en-US",
                    smart_format=True,
                    encoding="linear16",
                    channels=1,
                    sample_rate=16000
                )
            
            # Start live client connection
            dg_connection = self.client.listen.live.v("1")
            return dg_connection, options
        except Exception as e:
            print(f"Deepgram Live STT Connection Error: {e}")
            raise e
