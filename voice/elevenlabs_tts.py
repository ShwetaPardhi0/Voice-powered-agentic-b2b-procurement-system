import os
from dotenv import load_dotenv
from elevenlabs import ElevenLabs, VoiceSettings

load_dotenv()


class ElevenLabsTTS:
    """Converts procurement agent text replies into speech audio."""

    # A professional, confident voice suited for procurement scenarios
    DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # "Adam" – calm, business-like

    def __init__(self, api_key: str = None, voice_id: str = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY must be configured in environment.")
        self.client = ElevenLabs(api_key=self.api_key)
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID

    def synthesize(self, text: str, output_path: str = None) -> bytes:
        """
        Converts text to speech and optionally saves a WAV file.

        Args:
            text: Plain text to convert to speech.
            output_path: Optional path to write audio bytes to a file.

        Returns:
            Raw audio bytes (MP3 stream).
        """
        try:
            audio_stream = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                voice_settings=VoiceSettings(
                    stability=0.60,
                    similarity_boost=0.80,
                    style=0.0,
                    use_speaker_boost=True
                ),
                model_id="eleven_multilingual_v2",
            )

            audio_bytes = b"".join(chunk for chunk in audio_stream)

            if output_path:
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
                print(f"[TTS] Audio saved to: {output_path}")

            return audio_bytes

        except Exception as e:
            print(f"ElevenLabs TTS Error: {e}")
            raise e
