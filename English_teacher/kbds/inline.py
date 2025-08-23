from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_lesson_buttons_keyboard() -> InlineKeyboardMarkup:

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        # [
        #     InlineKeyboardButton(
        #         text="📚 Учиться по уроку", 
        #         callback_data="learn_lesson"
        #     )
        # ],
        [
            InlineKeyboardButton(
                text="💬 Общаться с учителем", 
                callback_data="chat_with_teacher"
            )
        ]
    ])
    return keyboard

def get_lesson_buttons_keyboard_with_info() -> InlineKeyboardMarkup:

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📚 Учиться по уроку", 
                callback_data="learn_lesson"
            )
        ],
        [
            InlineKeyboardButton(
                text="💬 Общаться с учителем", 
                callback_data="chat_with_teacher"
            )
        ]
    ])
    return keyboard
