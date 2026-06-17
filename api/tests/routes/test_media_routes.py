"""
Тесты для api/src/routes/media.py.

Покрываем:
- POST /media/images/generate — success, BadRequestError (422), generic error (502),
  с user_id (счётчик), с imgbb_api_key (upload)
- POST /media/audio/transcribe — success, file too large (413)

Faker: prompt, file content, user_id, URL, durations.
"""

import io
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from faker import Faker
from openai import BadRequestError

fake = Faker()
Faker.seed(42)


# Helpers


def _fake_image_buffers(n: int = 1) -> list[BytesIO]:
    bufs = []
    for _ in range(n):
        b = BytesIO(fake.binary(length=128))
        b.name = "image.png"
        b.seek(0)
        bufs.append(b)
    return bufs


def _fake_audio_content(size_bytes: int = 1024) -> bytes:
    return fake.binary(length=size_bytes)


# POST /media/images/generate


class TestImagesGenerate:

    @pytest.mark.api
    def test_generate_returns_200_with_images_b64(self, api_client) -> None:
        buffers = _fake_image_buffers(1)

        with patch("routes.media.generate_images", new=AsyncMock(return_value=buffers)), \
             patch("routes.media.settings") as mock_settings:
            mock_settings.imgbb_api_key = ""
            resp = api_client.post(
                "/media/images/generate",
                json={
                    "prompt": fake.sentence(),
                    "n_images": 1,
                    "size": "1024x1024",
                    "quality": "medium",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "images_b64" in data
        assert len(data["images_b64"]) == 1
        assert isinstance(data["images_b64"][0], str)

    @pytest.mark.api
    def test_generate_multiple_images(self, api_client) -> None:
        n = fake.random_int(min=2, max=4)
        buffers = _fake_image_buffers(n)

        with patch("routes.media.generate_images", new=AsyncMock(return_value=buffers)), \
             patch("routes.media.settings") as mock_settings:
            mock_settings.imgbb_api_key = ""
            resp = api_client.post(
                "/media/images/generate",
                json={"prompt": fake.sentence(), "n_images": n,
                      "size": "1024x1024", "quality": "medium"},
            )

        assert resp.status_code == 200
        assert len(resp.json()["images_b64"]) == n

    @pytest.mark.api
    def test_generate_bad_request_returns_422(self, api_client) -> None:
        bad_req: Any = BadRequestError.__new__(BadRequestError)
        bad_req.message = "content_policy_violation"
        bad_req.body = None
        bad_req.response = None

        with patch("routes.media.generate_images",
                   new=AsyncMock(side_effect=bad_req)):
            resp = api_client.post(
                "/media/images/generate",
                json={"prompt": fake.sentence(), "n_images": 1,
                      "size": "1024x1024", "quality": "medium"},
            )

        assert resp.status_code == 422
        assert "moderation_blocked" in resp.json()["detail"]

    @pytest.mark.api
    def test_generate_generic_error_returns_502(self, api_client) -> None:
        with patch("routes.media.generate_images",
                   new=AsyncMock(side_effect=RuntimeError(fake.sentence()))):
            resp = api_client.post(
                "/media/images/generate",
                json={"prompt": fake.sentence(), "n_images": 1,
                      "size": "1024x1024", "quality": "medium"},
            )

        assert resp.status_code == 502

    @pytest.mark.api
    def test_generate_with_user_id_updates_counter(self, api_client, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        buffers = _fake_image_buffers(1)

        mock_increment = AsyncMock()
        with patch("routes.media.generate_images", new=AsyncMock(return_value=buffers)), \
             patch("routes.media.user_repo.increment_n_generated_images", mock_increment), \
             patch("routes.media.settings") as mock_settings:
            mock_settings.imgbb_api_key = ""
            resp = api_client.post(
                "/media/images/generate",
                json={"prompt": fake.sentence(), "n_images": 1,
                      "size": "1024x1024", "quality": "medium", "user_id": uid},
            )

        assert resp.status_code == 200
        mock_increment.assert_awaited_once()

    @pytest.mark.api
    def test_generate_with_imgbb_uploads(self, api_client, fake) -> None:
        buffers = _fake_image_buffers(1)
        imgbb_url = fake.url()

        with patch("routes.media.generate_images", new=AsyncMock(return_value=buffers)), \
             patch("routes.media.upload_to_imgbb", new=AsyncMock(return_value=imgbb_url)), \
             patch("routes.media.settings") as mock_settings:
            mock_settings.imgbb_api_key = fake.sha256()[:32]
            resp = api_client.post(
                "/media/images/generate",
                json={"prompt": fake.sentence(), "n_images": 1,
                      "size": "1024x1024", "quality": "medium"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert imgbb_url in data["imgbb_urls"]

    @pytest.mark.api
    def test_generate_imgbb_failure_does_not_break_response(self, api_client) -> None:
        buffers = _fake_image_buffers(1)

        with patch("routes.media.generate_images", new=AsyncMock(return_value=buffers)), \
             patch("routes.media.upload_to_imgbb",
                   new=AsyncMock(side_effect=RuntimeError("imgbb down"))), \
             patch("routes.media.settings") as mock_settings:
            mock_settings.imgbb_api_key = "some_key"
            resp = api_client.post(
                "/media/images/generate",
                json={"prompt": fake.sentence(), "n_images": 1,
                      "size": "1024x1024", "quality": "medium"},
            )

        assert resp.status_code == 200
        assert resp.json()["imgbb_urls"] == [""]

    @pytest.mark.api
    def test_faker_batch_prompts(self, api_client) -> None:
        for _ in range(3):
            prompt = fake.sentence()
            buffers = _fake_image_buffers(1)
            with patch("routes.media.generate_images",
                       new=AsyncMock(return_value=buffers)), \
                 patch("routes.media.settings") as mock_settings:
                mock_settings.imgbb_api_key = ""
                resp = api_client.post(
                    "/media/images/generate",
                    json={"prompt": prompt, "n_images": 1,
                          "size": "1024x1024", "quality": "medium"},
                )
            assert resp.status_code == 200

    @pytest.mark.api
    def test_missing_prompt_returns_422(self, api_client) -> None:
        resp = api_client.post(
            "/media/images/generate",
            json={"n_images": 1, "size": "1024x1024", "quality": "medium"},
        )
        assert resp.status_code == 422


# POST /media/audio/transcribe


class TestAudioTranscribe:

    @pytest.mark.api
    def test_transcribe_returns_text_and_duration(self, api_client, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        transcribed_text = fake.sentence()
        audio_content = _fake_audio_content(2048)

        with patch("routes.media.transcribe_audio",
                   new=AsyncMock(return_value=transcribed_text)), \
             patch("db.repositories.users.increment_n_transcribed_seconds", new=AsyncMock()):
            resp = api_client.post(
                "/media/audio/transcribe",
                params={"user_id": uid, "lang": "ru"},
                files={"file": ("voice.ogg", io.BytesIO(audio_content), "audio/ogg")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == transcribed_text
        assert data["duration_seconds"] > 0

    @pytest.mark.api
    def test_transcribe_duration_estimated_from_size(self, api_client, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        content = _fake_audio_content(4000)
        expected_duration = len(content) / 2000.0

        with patch("routes.media.transcribe_audio", new=AsyncMock(return_value="text")), \
             patch("db.repositories.users.increment_n_transcribed_seconds", new=AsyncMock()):
            resp = api_client.post(
                "/media/audio/transcribe",
                params={"user_id": uid, "lang": "ru"},
                files={"file": ("voice.ogg", io.BytesIO(content), "audio/ogg")},
            )

        assert resp.status_code == 200
        assert abs(resp.json()["duration_seconds"] - expected_duration) < 0.01

    @pytest.mark.api
    def test_transcribe_file_too_large_returns_413(self, api_client, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        huge_content = fake.binary(length=11_000_001)

        resp = api_client.post(
            "/media/audio/transcribe",
            params={"user_id": uid, "lang": "ru"},
            files={"file": ("big.ogg", io.BytesIO(huge_content), "audio/ogg")},
        )

        assert resp.status_code == 413

    @pytest.mark.api
    def test_transcribe_counter_failure_does_not_break_response(
        self, api_client, fake
    ) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        content = _fake_audio_content(1024)

        with patch("routes.media.transcribe_audio", new=AsyncMock(return_value="ok")), \
             patch("db.repositories.users.increment_n_transcribed_seconds",
                   new=AsyncMock(side_effect=RuntimeError("DB error"))):
            resp = api_client.post(
                "/media/audio/transcribe",
                params={"user_id": uid, "lang": "ru"},
                files={"file": ("voice.ogg", io.BytesIO(content), "audio/ogg")},
            )

        assert resp.status_code == 200

    @pytest.mark.api
    def test_transcribe_different_languages(self, api_client, fake) -> None:
        for lang in ["ru", "en", "de", "es"]:
            uid = fake.random_int(min=100_000, max=999_999_999)
            content = _fake_audio_content(512)
            with patch("routes.media.transcribe_audio",
                       new=AsyncMock(return_value=fake.sentence())), \
                 patch("db.repositories.users.increment_n_transcribed_seconds",
                       new=AsyncMock()):
                resp = api_client.post(
                    "/media/audio/transcribe",
                    params={"user_id": uid, "lang": lang},
                    files={"file": ("voice.ogg", io.BytesIO(content), "audio/ogg")},
                )
            assert resp.status_code == 200