import os
from dotenv import load_dotenv
from livekit.api import LiveKitAPI, AccessToken, VideoGrants

load_dotenv()


class LiveKitClient:
    """Manages LiveKit room access tokens and room lifecycle."""

    def __init__(self):
        self.api_key = os.getenv("LIVEKIT_API_KEY")
        self.api_secret = os.getenv("LIVEKIT_API_SECRET")
        self.livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in .env"
            )

    def generate_token(self, room_name: str, participant_name: str) -> str:
        """
        Issues a signed JWT access token for a LiveKit participant.

        Args:
            room_name: Name of the room to join.
            participant_name: Identity for the participant joining.

        Returns:
            JWT token string.
        """
        token = (
            AccessToken(self.api_key, self.api_secret)
            .with_identity(participant_name)
            .with_name(participant_name)
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
        )
        return token.to_jwt()

    async def list_rooms(self) -> list[str]:
        """Returns all active LiveKit room names."""
        async with LiveKitAPI(
            url=self.livekit_url,
            api_key=self.api_key,
            api_secret=self.api_secret,
        ) as api:
            rooms = await api.room.list_rooms()
            return [r.name for r in rooms.rooms]

    async def delete_room(self, room_name: str) -> None:
        """Deletes a LiveKit room and disconnects all participants."""
        async with LiveKitAPI(
            url=self.livekit_url,
            api_key=self.api_key,
            api_secret=self.api_secret,
        ) as api:
            await api.room.delete_room(room_name=room_name)
            print(f"[LiveKit] Room '{room_name}' deleted.")
