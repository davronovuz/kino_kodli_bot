from aiogram.fsm.state import State, StatesGroup


class AddMovieStates(StatesGroup):
    waiting_file = State()
    waiting_code = State()
    waiting_title = State()
    waiting_title_uz = State()
    waiting_year = State()
    waiting_quality = State()
    waiting_language = State()
    waiting_genre = State()
    waiting_description = State()
    waiting_poster = State()
    confirm = State()


class EditMovieStates(StatesGroup):
    select_field = State()
    waiting_value = State()


class BroadcastStates(StatesGroup):
    waiting_message = State()
    confirm = State()


class AddChannelStates(StatesGroup):
    waiting_channel = State()


class ImportStates(StatesGroup):
    waiting_method = State()
    waiting_group_id = State()
    waiting_forward = State()
    waiting_file = State()
    processing = State()


class SearchStates(StatesGroup):
    waiting_query = State()


class BanUserStates(StatesGroup):
    waiting_user_id = State()
