"""
Тесты для:
- api/src/services/image_generation.py — generate_image_b64, generate_image_url, generate_images
- api/src/services/image_processing.py — process_generated_image, upload_to_imgbb

Faker: prompts, URLs, binary content, API keys.
PIL.Image используется напрямую (tiny 4×4 PNG).
httpx мокируется через unittest.mock.
"""

import base64
import io
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


# Helpers


def _tiny_png_b64() -> str:
    """Реальный 4×4 белый PNG в base64 для тестирования PIL."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(255, 255, 255)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _tiny_png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _make_image_response(b64: str | None = None, url: str | None = None):
    """MagicMock для openai images.generate response."""
    item = MagicMock()
    item.b64_json = b64
    item.url = url
    resp = MagicMock()
    resp.data = [item]
    return resp


# services/image_generation.py


class TestGenerateImageB64:

    @pytest.mark.asyncio
    async def test_returns_data_uri_from_b64_json(self) -> None:
        from services.image_generation import generate_image_b64
        b64 = fake.sha256()
        resp = _make_image_response(b64=b64)
        with patch("services.image_generation.make_client") as mock_make:
            mock_client = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=resp)
            mock_make.return_value = mock_client
            result = await generate_image_b64(
                prompt=fake.sentence(), size="1024x1024", quality="medium"
            )
        assert result == f"data:image/png;base64,{b64}"

    @pytest.mark.asyncio
    async def test_downloads_and_encodes_when_url_returned(self) -> None:
        from services.image_generation import generate_image_b64
        img_url = fake.url()
        raw_bytes = fake.binary(length=64)
        resp = _make_image_response(url=img_url)

        mock_http_resp = MagicMock()
        mock_http_resp.raise_for_status = MagicMock()
        mock_http_resp.content = raw_bytes

        mock_http_ctx = AsyncMock()
        mock_http_ctx.__aenter__ = AsyncMock(return_value=mock_http_ctx)
        mock_http_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_http_ctx.get = AsyncMock(return_value=mock_http_resp)

        with patch("services.image_generation.make_client") as mock_make, \
             patch("services.image_generation.httpx.AsyncClient") as MockHttp:
            mock_client = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=resp)
            mock_make.return_value = mock_client
            MockHttp.return_value = mock_http_ctx

            result = await generate_image_b64(prompt=fake.sentence())

        expected_b64 = base64.b64encode(raw_bytes).decode()
        assert result == f"data:image/png;base64,{expected_b64}"

    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_data(self) -> None:
        from services.image_generation import generate_image_b64
        resp = _make_image_response(b64=None, url=None)

        with patch("services.image_generation.make_client") as mock_make:
            mock_client = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=resp)
            mock_make.return_value = mock_client
            with pytest.raises(ValueError, match="No image data"):
                await generate_image_b64(prompt=fake.sentence())

    @pytest.mark.asyncio
    async def test_faker_batch_prompts_succeed(self) -> None:
        from services.image_generation import generate_image_b64
        for _ in range(3):
            b64 = fake.sha256()
            resp = _make_image_response(b64=b64)
            with patch("services.image_generation.make_client") as mock_make:
                mock_client = MagicMock()
                mock_client.images.generate = AsyncMock(return_value=resp)
                mock_make.return_value = mock_client
                result = await generate_image_b64(
                    prompt=fake.sentence(), model="gpt-image-1.5"
                )
            assert result.startswith("data:image/png;base64,")


class TestGenerateImageUrl:

    @pytest.mark.asyncio
    async def test_returns_url_when_url_available(self) -> None:
        from services.image_generation import generate_image_url
        img_url = fake.url()
        resp = _make_image_response(url=img_url)

        with patch("services.image_generation.make_client") as mock_make:
            mock_client = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=resp)
            mock_make.return_value = mock_client
            result = await generate_image_url(prompt=fake.sentence())

        assert result == img_url

    @pytest.mark.asyncio
    async def test_returns_data_uri_fallback_when_no_url(self) -> None:
        from services.image_generation import generate_image_url
        b64 = fake.sha256()
        resp = _make_image_response(b64=b64)

        with patch("services.image_generation.make_client") as mock_make:
            mock_client = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=resp)
            mock_make.return_value = mock_client
            result = await generate_image_url(prompt=fake.sentence())

        assert result == f"data:image/png;base64,{b64}"


class TestGenerateImages:

    @pytest.mark.asyncio
    async def test_returns_list_of_bytesio_from_b64_json(self) -> None:
        from services.image_generation import generate_images
        raw = fake.binary(length=64)
        b64 = base64.b64encode(raw).decode()
        resp = _make_image_response(b64=b64)

        with patch("services.image_generation.make_client") as mock_make:
            mock_client = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=resp)
            mock_make.return_value = mock_client
            results = await generate_images(prompt=fake.sentence(), n_images=1)

        assert len(results) == 1
        results[0].seek(0)
        assert results[0].read() == raw

    @pytest.mark.asyncio
    async def test_returns_multiple_images(self) -> None:
        from services.image_generation import generate_images
        n = fake.random_int(min=2, max=4)

        items = []
        for _ in range(n):
            item = MagicMock()
            item.b64_json = base64.b64encode(fake.binary(length=32)).decode()
            item.url = None
            items.append(item)

        resp = MagicMock()
        resp.data = items

        with patch("services.image_generation.make_client") as mock_make:
            mock_client = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=resp)
            mock_make.return_value = mock_client
            results = await generate_images(
                prompt=fake.sentence(), n_images=n
            )

        assert len(results) == n
        for buf in results:
            assert isinstance(buf, BytesIO)

    @pytest.mark.asyncio
    async def test_generates_with_url_streaming(self) -> None:
        from services.image_generation import generate_images
        img_url = fake.url()
        raw_bytes = fake.binary(length=32)
        resp = _make_image_response(url=img_url)

        mock_stream_resp = AsyncMock()
        mock_stream_resp.raise_for_status = MagicMock()

        async def _fake_aiter_bytes(*a, **kw):
            yield raw_bytes

        mock_stream_resp.aiter_bytes = _fake_aiter_bytes

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_http_client = MagicMock()
        mock_http_client.stream = MagicMock(return_value=mock_stream_cm)

        mock_http_ctx = MagicMock()
        mock_http_ctx.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.image_generation.make_client") as mock_make, \
             patch("services.image_generation.httpx.AsyncClient", return_value=mock_http_ctx):
            mock_client = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=resp)
            mock_make.return_value = mock_client
            results = await generate_images(prompt=fake.sentence(), n_images=1)

        assert len(results) == 1


# services/image_processing.py


class TestProcessGeneratedImage:

    def test_converts_png_b64_to_webp(self) -> None:
        from services.image_processing import process_generated_image
        b64 = _tiny_png_b64()
        result = process_generated_image(b64)
        assert "data" in result
        assert "size_kb" in result
        assert isinstance(result["data"], str)
        assert isinstance(result["size_kb"], float)

    def test_strips_data_uri_prefix(self) -> None:
        from services.image_processing import process_generated_image
        b64 = _tiny_png_b64()
        data_uri = f"data:image/png;base64,{b64}"
        result = process_generated_image(data_uri)
        assert "data" in result
        assert result["data"] != ""

    def test_plain_b64_and_data_uri_give_same_result(self) -> None:
        from services.image_processing import process_generated_image
        b64 = _tiny_png_b64()
        r1 = process_generated_image(b64)
        r2 = process_generated_image(f"data:image/png;base64,{b64}")
        assert r1["data"] == r2["data"]

    def test_custom_quality_affects_size(self) -> None:
        from services.image_processing import process_generated_image
        b64 = _tiny_png_b64()
        r_low = process_generated_image(b64, quality=10)
        r_high = process_generated_image(b64, quality=95)
        # low quality → smaller size_kb (for non-trivial images)
        assert isinstance(r_low["size_kb"], float)
        assert isinstance(r_high["size_kb"], float)

    def test_output_is_valid_base64(self) -> None:
        from services.image_processing import process_generated_image
        result = process_generated_image(_tiny_png_b64())
        decoded = base64.b64decode(result["data"])
        assert len(decoded) > 0

    def test_faker_batch_images(self) -> None:
        from services.image_processing import process_generated_image
        b64 = _tiny_png_b64()
        for _ in range(3):
            result = process_generated_image(b64)
            assert result["data"]


class TestUploadToImgbb:

    @pytest.mark.asyncio
    async def test_returns_image_url_on_success(self) -> None:
        from services.image_processing import upload_to_imgbb
        api_key = fake.sha256()[:32]
        b64_data = fake.sha256()
        expected_url = fake.url()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"data": {"url": expected_url}})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.image_processing.httpx.AsyncClient", return_value=mock_ctx):
            result = await upload_to_imgbb(b64_data, api_key)

        assert result == expected_url

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self) -> None:
        from services.image_processing import upload_to_imgbb
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "error", request=httpx.Request("POST", "http://test"), response=MagicMock()
            )
        )
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.image_processing.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(httpx.HTTPStatusError):
                await upload_to_imgbb(fake.sha256(), fake.sha256()[:32])

    @pytest.mark.asyncio
    async def test_passes_api_key_as_param(self) -> None:
        from services.image_processing import upload_to_imgbb
        api_key = fake.sha256()[:32]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"data": {"url": fake.url()}})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.image_processing.httpx.AsyncClient", return_value=mock_ctx):
            await upload_to_imgbb(fake.sha256(), api_key)

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["params"]["key"] == api_key