from aiogram.fsm.state import State, StatesGroup


class ChatStates(StatesGroup):
    waiting_for_image_prompt = State()
