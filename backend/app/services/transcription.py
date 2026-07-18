import httpx

from app.config import settings

WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada — transcrição de áudio indisponível")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            WHISPER_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            files={"file": (filename, audio_bytes)},
            data={"model": "whisper-1", "language": "pt"},
        )
        response.raise_for_status()
        return response.json()["text"]
