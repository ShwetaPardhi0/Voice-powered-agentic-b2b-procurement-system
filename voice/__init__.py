"""
voice package
-------------
Provides modular components for the real-time procurement voice pipeline:
  - DeepgramSTT   : speech-to-text transcription
  - ElevenLabsTTS : text-to-speech synthesis
  - LiveKitClient : WebRTC room token management
  - AudioStream   : audio buffer/chunk utilities
  - VoicePipeline : end-to-end STT→Agent→TTS orchestration
"""

__all__ = [
    "DeepgramSTT",
    "ElevenLabsTTS",
    "LiveKitClient",
    "AudioStream",
    "VoicePipeline",
]


def __getattr__(name):
    """Lazy-load to avoid import errors when optional packages are missing."""
    if name == "DeepgramSTT":
        from voice.deepgram_stt import DeepgramSTT
        return DeepgramSTT
    if name == "ElevenLabsTTS":
        from voice.elevenlabs_tts import ElevenLabsTTS
        return ElevenLabsTTS
    if name == "LiveKitClient":
        from voice.livekit_client import LiveKitClient
        return LiveKitClient
    if name == "AudioStream":
        from voice.audio_stream import AudioStream
        return AudioStream
    if name == "VoicePipeline":
        from voice.pipeline import VoicePipeline
        return VoicePipeline
    raise AttributeError(f"module 'voice' has no attribute {name!r}")
