from aiogram.fsm.state import State, StatesGroup


class WhitelistStates(StatesGroup):
    waiting_for_user_id = State()