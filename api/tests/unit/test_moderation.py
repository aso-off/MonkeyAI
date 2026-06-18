"""Юнит-тесты для api/src/services/moderation.py.

OpenAI client заменён AsyncMock - реальные запросы не делаются.
settings патчится для контроля флагов и threshold'ов.
"""

import types
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.moderation import MODERATION_CATEGORIES, moderate_content

# Helpers

def _attr_name(category: str) -> str:
    """Преобразует имя категории в имя атрибута (как в модуле)."""
    return category.replace("/", "_").replace("-", "_")

def _make_moderation_response(
    flagged: bool = False,
    flagged_categories: dict | None = None,
    scores: dict | None = None,
) -> MagicMock:
    """Строит mock OpenAI ModerationResponse с нужными значениями."""
    flagged_categories = flagged_categories or {}
    scores = scores or {}

    result = MagicMock()
    result.flagged = flagged
    result.category_scores.model_extra = {}

    for category in MODERATION_CATEGORIES:
        attr = _attr_name(category)
        setattr(result.categories, attr, flagged_categories.get(category, False))
        setattr(result.category_scores, attr, scores.get(category, 0.01))

    response = MagicMock()
    response.results = [result]
    return response

@pytest.fixture
def settings_enabled():
    with patch("services.moderation.settings", types.SimpleNamespace(
        enable_content_moderation=True,
        moderation_thresholds={},
    )):
        yield

@pytest.fixture
def settings_disabled():
    with patch("services.moderation.settings", types.SimpleNamespace(
        enable_content_moderation=False,
        moderation_thresholds={},
    )):
        yield

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.moderations.create = AsyncMock()
    with patch("services.moderation.make_client", return_value=client):
        yield client

# Модерация отключена

class TestModerationDisabled:
    @pytest.mark.unit
    async def test_disabled_returns_false_immediately(self, settings_disabled, fake) -> None:
        flagged, cats, scores = await moderate_content(text=fake.sentence())
        assert flagged is False
        assert cats == {}
        assert scores == {}

    @pytest.mark.unit
    async def test_disabled_does_not_call_openai(self, settings_disabled, mock_client, fake) -> None:
        await moderate_content(text=fake.sentence())
        mock_client.moderations.create.assert_not_awaited()

# Пустой ввод

class TestEmptyInput:
    @pytest.mark.unit
    async def test_no_text_no_image_returns_false(self, settings_enabled, mock_client) -> None:
        flagged, cats, scores = await moderate_content()
        assert flagged is False and cats == {} and scores == {}
        mock_client.moderations.create.assert_not_awaited()

    @pytest.mark.unit
    async def test_whitespace_only_text_returns_false(self, settings_enabled, mock_client) -> None:
        flagged, cats, scores = await moderate_content(text="   ")
        assert flagged is False
        mock_client.moderations.create.assert_not_awaited()

    @pytest.mark.unit
    async def test_empty_string_text_returns_false(self, settings_enabled, mock_client) -> None:
        flagged, cats, scores = await moderate_content(text="")
        assert flagged is False

# Чистый контент

class TestCleanContent:
    @pytest.mark.unit
    async def test_clean_text_returns_not_flagged(self, settings_enabled, mock_client, fake) -> None:
        mock_client.moderations.create.return_value = _make_moderation_response(flagged=False)
        flagged, cats, scores = await moderate_content(text=fake.sentence())
        assert flagged is False
        assert cats == {}

    @pytest.mark.unit
    async def test_clean_content_returns_scores(self, settings_enabled, mock_client, fake) -> None:
        response = _make_moderation_response(flagged=False, scores={"harassment": 0.01})
        mock_client.moderations.create.return_value = response
        _, _, scores = await moderate_content(text=fake.sentence())
        assert "harassment" in scores
        assert scores["harassment"] == pytest.approx(0.01)

    @pytest.mark.unit
    async def test_openai_called_with_text_input(self, settings_enabled, mock_client, fake) -> None:
        mock_client.moderations.create.return_value = _make_moderation_response()
        text = fake.sentence()
        await moderate_content(text=text)
        call_kwargs = mock_client.moderations.create.call_args[1]
        input_data = call_kwargs["input"]
        assert any(item.get("type") == "text" for item in input_data)

    @pytest.mark.unit
    async def test_openai_called_with_correct_model(self, settings_enabled, mock_client, fake) -> None:
        mock_client.moderations.create.return_value = _make_moderation_response()
        await moderate_content(text=fake.sentence())
        call_kwargs = mock_client.moderations.create.call_args[1]
        assert call_kwargs["model"] == "omni-moderation-latest"

# Флагированный контент

class TestFlaggedContent:
    @pytest.mark.unit
    async def test_flagged_by_openai_returns_true(self, settings_enabled, mock_client, fake) -> None:
        response = _make_moderation_response(
            flagged=True,
            flagged_categories={"harassment": True},
            scores={"harassment": 0.9},
        )
        mock_client.moderations.create.return_value = response
        flagged, cats, scores = await moderate_content(text=fake.sentence())
        assert flagged is True
        assert "harassment" in cats

    @pytest.mark.unit
    async def test_score_above_default_threshold_flags(self, settings_enabled, mock_client, fake) -> None:
        # Дефолтный threshold = 0.5, score = 0.8 > должен флагировать
        response = _make_moderation_response(
            flagged=False,
            scores={"violence": 0.8},
        )
        mock_client.moderations.create.return_value = response
        flagged, cats, scores = await moderate_content(text=fake.sentence())
        assert flagged is True
        assert "violence" in cats

    @pytest.mark.unit
    async def test_score_below_threshold_not_flagged(self, mock_client, fake) -> None:
        response = _make_moderation_response(
            flagged=False,
            scores={"harassment": 0.7},  # 0.7 < 0.9 > не флаг
        )
        mock_client.moderations.create.return_value = response
        with patch("services.moderation.settings", types.SimpleNamespace(
            enable_content_moderation=True,
            moderation_thresholds={"harassment": 0.9},
        )):
            flagged, cats, _ = await moderate_content(text=fake.sentence())
        assert flagged is False

    @pytest.mark.unit
    async def test_custom_threshold_respected(self, mock_client, fake) -> None:
        response = _make_moderation_response(
            flagged=False,
            scores={"hate": 0.5},  # 0.5 > 0.3 > флаг
        )
        mock_client.moderations.create.return_value = response
        with patch("services.moderation.settings", types.SimpleNamespace(
            enable_content_moderation=True,
            moderation_thresholds={"hate": 0.3},
        )):
            flagged, cats, _ = await moderate_content(text=fake.sentence())
        assert flagged is True
        assert "hate" in cats

    @pytest.mark.unit
    async def test_multiple_categories_flagged(self, settings_enabled, mock_client, fake) -> None:
        response = _make_moderation_response(
            flagged=True,
            flagged_categories={"harassment": True, "violence": True},
            scores={"harassment": 0.9, "violence": 0.8},
        )
        mock_client.moderations.create.return_value = response
        flagged, cats, scores = await moderate_content(text=fake.sentence())
        assert flagged is True
        assert "harassment" in cats and "violence" in cats

# Изображение

class TestImageInput:
    @pytest.mark.unit
    async def test_image_buffer_included_in_input(self, settings_enabled, mock_client) -> None:
        mock_client.moderations.create.return_value = _make_moderation_response()
        buf = BytesIO(b"\xff\xd8\xff" + b"\x00" * 100)  # fake JPEG header
        await moderate_content(image_buffer=buf)
        call_kwargs = mock_client.moderations.create.call_args[1]
        input_data = call_kwargs["input"]
        assert any(item.get("type") == "image_url" for item in input_data)

    @pytest.mark.unit
    async def test_image_buffer_position_restored(self, settings_enabled, mock_client) -> None:
        mock_client.moderations.create.return_value = _make_moderation_response()
        buf = BytesIO(b"\xff\xd8\xff" + b"\x00" * 100)
        buf.seek(10)
        await moderate_content(image_buffer=buf)
        assert buf.tell() == 10  # позиция восстановлена

    @pytest.mark.unit
    async def test_text_and_image_both_sent(self, settings_enabled, mock_client, fake) -> None:
        mock_client.moderations.create.return_value = _make_moderation_response()
        buf = BytesIO(b"\xff\xd8\xff" + b"\x00" * 50)
        await moderate_content(text=fake.sentence(), image_buffer=buf)
        call_kwargs = mock_client.moderations.create.call_args[1]
        types_in_input = [item["type"] for item in call_kwargs["input"]]
        assert "text" in types_in_input and "image_url" in types_in_input

# Обработка ошибок

class TestErrorHandling:
    @pytest.mark.unit
    async def test_openai_error_returns_allow_through(self, settings_enabled, mock_client, fake) -> None:
        mock_client.moderations.create.side_effect = Exception("API timeout")
        flagged, cats, scores = await moderate_content(text=fake.sentence())
        # allow-through: возвращаем False при ошибке
        assert flagged is False
        assert cats == {} and scores == {}

    @pytest.mark.unit
    async def test_connection_error_returns_allow_through(self, settings_enabled, mock_client, fake) -> None:
        mock_client.moderations.create.side_effect = ConnectionError("network down")
        flagged, _, _ = await moderate_content(text=fake.sentence())
        assert flagged is False

    @pytest.mark.unit
    async def test_faker_multiple_texts_no_crash(self, settings_enabled, mock_client, fake) -> None:
        mock_client.moderations.create.return_value = _make_moderation_response(flagged=False)
        for _ in range(5):
            flagged, _, _ = await moderate_content(text=fake.paragraph())
            assert isinstance(flagged, bool)
