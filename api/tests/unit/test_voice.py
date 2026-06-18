"""Юнит-тесты для api/src/services/voice.py - transcribe_audio."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from services.voice import transcribe_audio


@pytest.fixture
def mock_client(mocker):
    client = MagicMock()
    client.audio.transcriptions.create = AsyncMock()
    mocker.patch("services.voice.make_client", return_value=client)
    return client

class TestTranscribeAudio:
    @pytest.mark.unit
    async def test_returns_transcribed_text(self, mock_client, fake) -> None:
        expected = fake.sentence()
        mock_client.audio.transcriptions.create.return_value = MagicMock(text=expected)
        result = await transcribe_audio(MagicMock(), lang="ru")
        assert result == expected

    @pytest.mark.unit
    async def test_uses_whisper_model(self, mock_client) -> None:
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="ok")
        await transcribe_audio(MagicMock(), lang="en")
        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["model"] == "whisper-1"

    @pytest.mark.unit
    async def test_passes_language_param(self, mock_client) -> None:
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="ok")
        await transcribe_audio(MagicMock(), lang="de")
        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["language"] == "de"

    @pytest.mark.unit
    async def test_default_lang_is_ru(self, mock_client) -> None:
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="ok")
        await transcribe_audio(MagicMock())
        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["language"] == "ru"

    @pytest.mark.unit
    async def test_empty_response_text_returns_empty_string(self, mock_client) -> None:
        mock_client.audio.transcriptions.create.return_value = MagicMock(text=None)
        result = await transcribe_audio(MagicMock())
        assert result == ""

    @pytest.mark.unit
    async def test_openai_error_returns_empty_string(self, mock_client) -> None:
        mock_client.audio.transcriptions.create.side_effect = Exception("API error")
        result = await transcribe_audio(MagicMock())
        assert result == ""

    @pytest.mark.unit
    async def test_connection_error_returns_empty_string(self, mock_client) -> None:
        mock_client.audio.transcriptions.create.side_effect = ConnectionError("down")
        result = await transcribe_audio(MagicMock())
        assert result == ""

    @pytest.mark.unit
    @pytest.mark.parametrize("lang", ["ru", "en", "de", "es", "fr"])
    async def test_all_supported_langs(self, mock_client, lang: str) -> None:
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="text")
        result = await transcribe_audio(MagicMock(), lang=lang)
        assert isinstance(result, str)
