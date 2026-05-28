import logging
import random
from typing import Dict

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


class MonkeyStickers:
    """Управление стикерами с обезьянками."""

    # Категории "промежуточных" стикеров (отправляются во время обработки и удаляются потом)
    PROCESSING_CATEGORIES = {"thinking", "loading", "generating", "processing"}

    STICKERS: Dict[str, list[str]] = {
        "happy": [
            "CAACAgIAAxkBAAEOHOxn2chHIhFjSfXVEYS-bEO_S9kMtgACsQADMNSdEQcvTnZqWCSfNgQ",
            "CAACAgIAAxkBAAEOHOpn2cgnTHgv_Uisv1lxaBteeJECPgACswADMNSdET9j0fISlCKpNgQ",
            "CAACAgIAAxkBAAEOHRZn2dILNm7Y5ZFE606JDczu5K4tpwACrQADMNSdEfjbpoDStv0vNgQ",
            "CAACAgIAAxkBAAEOHRhn2dIdIN1mlMozaLB7NknpscHSmwACowADMNSdEWmtlTFeBowaNgQ",
        ],
        "thinking": [
            "CAACAgIAAxkBAAEOHNNn2cIqJbE69tXNXpoCf8h07XNBsAACpAADMNSdEU7MT7Gv4LoZNgQ",
            "CAACAgIAAxkBAAEOHPBn2chze6ZSn3wr50GTIOkI43Ey6AACnwADMNSdEcfeARK5-qXnNgQ",
        ],
        "surprised": [
            "CAACAgIAAxkBAAEOHPRn2ciYeD785pWTuY1-hm-U_L_B3AACmgADMNSdEfm7SJpr7g2zNgQ",
            "CAACAgIAAxkBAAEOHPZn2ci21Hn4DO3dj00DyN7OmUm35gACtQADMNSdERXZEmWP4ojaNgQ",
        ],
        "sad": [
            "CAACAgIAAxkBAAEOHPpn2ckQSCxVbzlG_gnH_57XiF1WWgACtAADMNSdERE0Tqq-mR_8NgQ",
        ],
        "error": [
            "CAACAgIAAxkBAAEOHPhn2cj1k6MAAZ-VSRMQCnL8Q7SQZgYAAqwAAzDUnRHh6uvv6RknuDYE",
            "CAACAgIAAxkBAAEOHQhn2czAIhgfPpktfOMTbZZO5yhrSQACqwADMNSdEc5fk4AVkl-RNgQ",
        ],
        "hello": [
            "CAACAgIAAxkBAAEOHP5n2ck0fJWGCHA7HxGHGeQZORYOAAOlAAMw1J0ROBvDY5d2HS02BA",
            "CAACAgIAAxkBAAEOHQpn2czWpJzWp6CiHadK88HCrnjW-wACoAADMNSdEXWwd3YpWMKTNgQ",
            "CAACAgIAAxkBAAEOHPRn2ciYeD785pWTuY1-hm-U_L_B3AACmgADMNSdEfm7SJpr7g2zNgQ",
        ],
        "loading": [
            "CAACAgIAAxkBAAEOHQABZ9nJPgPQiP1PLYWiFJCJUMfjI1oAAq4AAzDUnRHQylj5TnG01TYE",
        ],
        "generating": [
            "CAACAgIAAxkBAAEOHQJn2clMEor36Gr0lHtOi8ALqj5ehwACnAADMNSdEZATPuFz2Nb5NgQ",
        ],
        "processing": [
            "CAACAgIAAxkBAAEOHQRn2cmOqXTEIFTBI7_bJBWl464NFQACpwADMNSdEd5jQjYYM_sQNgQ",
        ],
    }

    def __init__(self) -> None:
        # chat_id → message_id промежуточного стикера
        self._processing: Dict[int, int] = {}

    def get_random(self, emotion: str | None = None) -> str:
        pool = self.STICKERS.get(emotion or "happy") or self.STICKERS["happy"]
        return random.choice(pool)

    async def send(
        self,
        bot: Bot,
        chat_id: int,
        emotion: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> bool:
        try:
            is_processing = emotion in self.PROCESSING_CATEGORIES

            if not is_processing:
                await self.delete_processing(bot, chat_id)

            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.CHOOSE_STICKER)

            sent = await bot.send_sticker(
                chat_id=chat_id,
                sticker=self.get_random(emotion),
                reply_to_message_id=reply_to_message_id,
            )

            if is_processing:
                self._processing[chat_id] = sent.message_id
                logger.debug("Sticker saved: emotion=%s chat_id=%d msg_id=%d", emotion, chat_id, sent.message_id)

            logger.debug("Sticker sent: emotion=%s chat_id=%d", emotion, chat_id)
            return True

        except TelegramAPIError as e:
            logger.error("Failed to send sticker: %s", e)
            return False

    async def delete_processing(self, bot: Bot, chat_id: int) -> bool:
        message_id = self._processing.pop(chat_id, None)
        if message_id is None:
            return False
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.debug("Processing sticker deleted: chat_id=%d msg_id=%d", chat_id, message_id)
            return True
        except TelegramAPIError as e:
            logger.warning("Failed to delete processing sticker: %s", e)
            return False


# Глобальный синглтон — используется во всех роутерах
monkey = MonkeyStickers()
