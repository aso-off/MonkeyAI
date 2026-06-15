import base64
import logging
from io import BytesIO

from core.config import settings
from services.openai import make_client

logger = logging.getLogger(__name__)

MODERATION_CATEGORIES = [
    "harassment", "harassment/threatening",
    "hate", "hate/threatening",
    "sexual", "sexual/minors",
    "violence", "violence/graphic",
    "self-harm", "self-harm/intent", "self-harm/instructions",
    "illicit", "illicit/violent",
]


async def moderate_content(
    text: str | None = None,
    image_buffer: BytesIO | None = None,
) -> tuple[bool, dict, dict]:
    try:
        if not settings.enable_content_moderation:
            return False, {}, {}

        input_data: list[dict] = []
        if text and text.strip():
            input_data.append({"type": "text", "text": text})
        if image_buffer:
            pos = image_buffer.tell()
            image_buffer.seek(0)
            encoded = base64.b64encode(image_buffer.read()).decode("utf-8")
            image_buffer.seek(pos)
            input_data.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
            })

        if not input_data:
            return False, {}, {}

        client = make_client()
        response = await client.moderations.create(
            model="omni-moderation-latest",
            input=input_data,
        )

        result = response.results[0]
        thresholds: dict = settings.moderation_thresholds or {}
        is_flagged = result.flagged
        flagged_categories: dict = {}
        scores: dict = {}

        for category in MODERATION_CATEGORIES:
            attr = category.replace("/", "_").replace("-", "_")

            if getattr(result.categories, attr, False):
                flagged_categories[category] = True

            score = getattr(result.category_scores, attr, None)
            if isinstance(score, (int, float)):
                scores[category] = score
                if score > thresholds.get(category, 0.5):
                    is_flagged = True
                    flagged_categories[category] = True

        if hasattr(result.category_scores, "model_extra") and isinstance(
            result.category_scores.model_extra, dict
        ):
            for category, score in result.category_scores.model_extra.items():
                if isinstance(score, (int, float)):
                    scores[category] = score
                    base = category.split("/")[0]
                    threshold = thresholds.get(category, thresholds.get(base, 0.5))
                    if score > threshold:
                        is_flagged = True
                        flagged_categories[category] = True

        if is_flagged:
            logger.info("Content rejected. Categories: %s", flagged_categories)

        return is_flagged, flagged_categories, scores

    except Exception:
        logger.exception("Content moderation failed — allowing content through")
        return False, {}, {}