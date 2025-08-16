import json
import asyncio
from aiogram.types import FSInputFile, InputMediaAudio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, Voice, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from text.text import (
    welcome_text, return_welcome_text, voice_error_text, start_first_text,
    all_topics_completed_text, openai_error_text, homework_assigned_text,
    homework_error_text, homework_completed_text, send_voice_text
)

from database.models import User, Topic, MessageHistory, Homework
from ai.ai import openai_client
from speech.whisper_engine import transcribe_audio, generate_speech, save_audio_to_file
from handlers.sending_data import (
    save_lesson_dialog, save_homework, send_lesson_summary_to_group,
    send_homework_response_to_group, get_lesson_dialogs, update_homework_answer
)

router_user_private = Router()


class LessonState(StatesGroup):
    """Состояния для урока английского языка"""
    waiting_for_voice = State()  # Ожидание голосового сообщения
    in_lesson = State()          # В процессе урока
    waiting_for_correction = State()  # Ожидание ответа на работу над ошибками
    lesson_completed = State()   # Урок завершён

# Словарь для хранения таймеров ожидания
waiting_timers = {}


@router_user_private.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession):
    """
    Обработчик команды /start
    """
    user_id = message.from_user.id
    
    # Проверяем, есть ли пользователь в БД
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Создаём нового пользователя
        user = User(
            id=user_id,
            progress="[]"
        )
        session.add(user)
        await session.commit()
        
        message_text = welcome_text
    else:
        message_text = return_welcome_text
    
    await message.answer(message_text)

@router_user_private.message(F.voice)
async def handle_voice_message(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик голосовых сообщений
    """
    user_id = message.from_user.id
    voice = message.voice
    
    if not voice:
        await message.answer(voice_error_text)
        return
    
    # Отменяем таймер ожидания если он был
    if user_id in waiting_timers:
        waiting_timers[user_id].cancel()
        del waiting_timers[user_id]
    
    # Получаем данные состояния
    data = await state.get_data()
    lesson_iteration = data.get("lesson_iteration", 1)
    
    # Получаем или создаём пользователя
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer(start_first_text)
        return
    
    # Скачиваем голосовое сообщение
    try:
        file = await message.bot.get_file(voice.file_id)
        file_path = file.file_path
        
        # Создаём временный файл для сохранения голосового сообщения
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
            temp_path = temp_file.name
        
        # Скачиваем файл
        await message.bot.download_file(file_path, temp_path)
        
        # Транскрибируем голосовое сообщение в текст с помощью OpenAI Whisper
        try:
            user_text = await transcribe_audio(temp_path)
            if not user_text.strip():
                user_text = "Hello, teacher!"  # Fallback если Whisper не распознал
        except Exception as e:
            print(f"Ошибка при транскрибации OpenAI Whisper: {e}")
            user_text = "Hello, teacher!"  # Fallback
        
        # Удаляем временный файл
        try:
            os.unlink(temp_path)
        except:
            pass
            
    except Exception as e:
        print(f"Ошибка при скачивании голосового сообщения: {e}")
        user_text = "Hello, teacher!"  # Fallback
    
    # Получаем текущую тему
    current_topic = None
    if user and user.current_topic_id:
        topic_result = await session.execute(
            select(Topic).where(Topic.id == user.current_topic_id)
        )
        current_topic = topic_result.scalar_one_or_none()
    
    # Если нет текущей темы, выбираем следующую непройденную
    if not current_topic:
        current_topic = await get_next_topic(session, user)
        if current_topic:
            # Обновляем пользователя через update
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(current_topic_id=current_topic.id)
            )
            await session.commit()
    
    if not current_topic:
        await message.answer(all_topics_completed_text)
        await state.clear()
        return
    
    # Получаем историю сообщений (последние 20)
    history_result = await session.execute(
        select(MessageHistory)
        .where(MessageHistory.user_id == user_id)
        .order_by(MessageHistory.timestamp.desc())
        .limit(20)
    )
    history_messages = history_result.scalars().all()
    
    # Преобразуем в формат для OpenAI
    conversation_history = []
    for msg in reversed(history_messages):  # В хронологическом порядке
        conversation_history.append({
            "role": str(msg.role),
            "content": str(msg.content)
        })
    
    # Проверяем, это первая итерация или вторая
    if lesson_iteration == 1:
        # Первая итерация - проверяем произношение и даём советы
        await handle_first_iteration(message, state, session, user_id, user_text, current_topic, conversation_history, voice.file_id)
    else:
        # Вторая итерация - проверяем исправления
        await handle_second_iteration(message, state, session, user_id, user_text, current_topic, conversation_history, voice.file_id)


async def handle_first_iteration(message: Message, state: FSMContext, session: AsyncSession, user_id: int, user_text: str, current_topic: Topic, conversation_history: list, voice_file_id: str):
    """
    Обрабатывает первую итерацию урока
    """
    # Генерируем интеллектуальный ответ с проверкой
    try:
        ai_response, feedback = await openai_client.generate_intelligent_response(
            user_message=user_text,
            conversation_history=conversation_history,
            current_topic={
                "title": str(current_topic.title),
                "description": str(current_topic.description),
                "tasks": json.loads(str(current_topic.tasks))
            }
        )
    except Exception as e:
        print(f"Ошибка при работе с OpenAI: {e}")
        ai_response = "I'm sorry, there was an error. Please try again later."
        feedback = {
            "is_correct": True,
            "feedback": "Отлично! 👍",
            "correct_answer": user_text,
            "explanation": ""
        }
    
    # Формируем ответ с обратной связью
    response_text = f"💡 Совет\n\n{feedback.get('feedback', '')}\n\n"
    if not feedback.get('is_correct', True):
        response_text += f"Правильный ответ: {feedback.get('correct_answer', '')}\n\n"
        response_text += f"Объяснение: {feedback.get('explanation', '')}\n\n"
    
    # Генерируем голосовое сообщение от учителя
    try:
        audio_bytes = await generate_speech(ai_response)
        if audio_bytes:
            # Сохраняем аудио в файл
            audio_path = await save_audio_to_file(audio_bytes, f"teacher_response_{user_id}.mp3")
            if audio_path:
                # Отправляем голосовое сообщение
                await message.bot.send_voice(
                    chat_id=user_id,
                    voice=FSInputFile(audio_path),
                    caption=ai_response
                )
                # Удаляем временный файл
                try:
                    os.unlink(audio_path)
                except:
                    pass
            else:
                # Если не удалось сохранить аудио, отправляем только текст
                await message.answer(ai_response)
        else:
            # Если не удалось сгенерировать аудио, отправляем только текст
            await message.answer(ai_response)
    except Exception as e:
        print(f"Ошибка при генерации голосового сообщения: {e}")
        await message.answer(ai_response)
    
    # Отправляем обратную связь
    await message.answer(response_text)
    
    # Создаём inline кнопку для работы над ошибками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Работа над ошибками", callback_data="work_on_errors")]
    ])
    await message.answer("Повторим?", reply_markup=keyboard)
    
    # Сохраняем диалог в базу данных
    await save_lesson_dialog(
        session=session,
        user_id=user_id,
        user_message=user_text,
        ai_response=ai_response,
        voice_file_id=voice_file_id
    )
    
    # Обновляем дату последнего урока
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(last_lesson_date=datetime.utcnow())
    )
    
    await session.commit()
    
    # Устанавливаем таймер ожидания (3 минуты)
    await set_waiting_timer(message, user_id, 3, "first_reminder", session)

async def handle_second_iteration(message: Message, state: FSMContext, session: AsyncSession, user_id: int, user_text: str, current_topic: Topic, conversation_history: list, voice_file_id: str):
    """
    Обрабатывает вторую итерацию урока
    """
    # Генерируем интеллектуальный ответ с проверкой для второй итерации
    try:
        ai_response, feedback = await openai_client.generate_intelligent_response(
            user_message=user_text,
            conversation_history=conversation_history,
            current_topic={
                "title": str(current_topic.title),
                "description": str(current_topic.description),
                "tasks": json.loads(str(current_topic.tasks))
            }
        )
    except Exception as e:
        print(f"Ошибка при проверке ответа: {e}")
        feedback = {
            "is_correct": True,
            "feedback": "Отлично! 👍 Вы улучшились!",
            "correct_answer": user_text,
            "explanation": ""
        }
        ai_response = "Great job! You've improved a lot!"
    
    # Отправляем согласованный ответ от бота
    await message.answer(ai_response)
    
    # Формируем и отправляем обратную связь
    response_text = f"💡 Результат второй попытки\n\n{feedback.get('feedback', '')}\n\n"
    if not feedback.get('is_correct', True):
        response_text += f"Правильный ответ: {feedback.get('correct_answer', '')}\n\n"
        response_text += f"Объяснение: {feedback.get('explanation', '')}\n\n"
    
    await message.answer(response_text)
    
    # Сохраняем диалог в базу данных
    await save_lesson_dialog(
        session=session,
        user_id=user_id,
        user_message=user_text,
        ai_response="Second iteration feedback",
        voice_file_id=voice_file_id
    )
    
    await session.commit()
    
    # Завершаем урок и выдаём домашнее задание
    await give_homework(message, state, session, user_id, current_topic, conversation_history)


@router_user_private.callback_query(F.data == "work_on_errors")
async def work_on_errors_callback(callback, state: FSMContext):
    """
    Обработчик кнопки "Работа над ошибками"
    """
    user_id = callback.from_user.id
    
    # Отменяем таймер ожидания если он был
    if user_id in waiting_timers:
        waiting_timers[user_id].cancel()
        del waiting_timers[user_id]
    
    # Обновляем состояние для второй итерации
    await state.update_data(lesson_iteration=2)
    await state.set_state(LessonState.waiting_for_voice)
    
    await callback.message.answer("🎤 Отлично! Теперь повторите те же предложения, но постарайтесь исправить ошибки. Отправьте голосовое сообщение!")


async def set_waiting_timer(message: Message, user_id: int, minutes: int, reminder_type: str, session: AsyncSession):
    """
    Устанавливает таймер ожидания
    """
    async def send_reminder():
        try:
            if reminder_type == "first_reminder":
                await message.bot.send_message(
                    chat_id=user_id,
                    text="Эй! Мы так классно общались. Давай продолжим? 🚀"
                )
                # Устанавливаем второй таймер (ещё 2 минуты)
                await set_waiting_timer(message, user_id, 2, "final_reminder", session)
            elif reminder_type == "final_reminder":
                await message.bot.send_message(
                    chat_id=user_id,
                    text="🏁 Кажется, пора закончить разговор, но ты всегда можешь вернуться, когда захочешь! 😊"
                )
                # Завершаем урок
                await finish_lesson_early(message, user_id, session)
        except Exception as e:
            print(f"Ошибка при отправке напоминания: {e}")
        finally:
            if user_id in waiting_timers:
                del waiting_timers[user_id]
    
    # Создаём таймер
    timer = asyncio.create_task(asyncio.sleep(minutes * 60))
    waiting_timers[user_id] = timer
    
    try:
        await timer
        await send_reminder()
    except asyncio.CancelledError:
        # Таймер был отменён
        pass


async def finish_lesson_early(message: Message, user_id: int, session: AsyncSession):
    """
    Завершает урок досрочно с персонализированным сообщением
    """
    try:
        # Получаем информацию о пользователе
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Получаем последние сообщения для контекста
        history_result = await session.execute(
            select(MessageHistory)
            .where(MessageHistory.user_id == user_id)
            .order_by(MessageHistory.timestamp.desc())
            .limit(5)
        )
        recent_messages = history_result.scalars().all()
        
        # Создаём краткое описание урока
        conversation_summary = "Урок был прерван из-за неактивности ученика"
        if recent_messages:
            topics = [msg.content[:50] + "..." for msg in recent_messages[:3]]
            conversation_summary = f"Обсуждали: {', '.join(topics)}"
        
        # Генерируем персонализированное сообщение
        user_name = message.from_user.full_name or "ученик"
        end_message = await openai_client.generate_lesson_end_message(
            conversation_summary=conversation_summary,
            user_name=user_name
        )
        
        await message.bot.send_message(
            chat_id=user_id,
            text=end_message
        )
    except Exception as e:
        print(f"Ошибка при завершении урока: {e}")
        # Fallback сообщение
        await message.bot.send_message(
            chat_id=user_id,
            text="Привет! Ты хорошо говоришь по-английски. Продолжай практиковаться, и ты станешь еще лучше! 😊"
        )

async def get_next_topic(session: AsyncSession, user: User):
    """
    Получает следующую непройденную тему
    """
    # Получаем список пройденных тем
    if not user:
        return None
    
    progress_str = str(user.progress) if user.progress else "[]"
    completed_topics = json.loads(progress_str)
    
    # Ищем непройденную тему
    result = await session.execute(
        select(Topic)
        .where(Topic.id.notin_(completed_topics))
        .order_by(Topic.id)
        .limit(1)
    )
    
    return result.scalar_one_or_none()

async def give_homework(
    message: Message, 
    state: FSMContext,
    session: AsyncSession, 
    user_id: int, 
    current_topic: Topic, 
    conversation_history: list
):
    """
    Выдаёт домашнее задание
    """
    try:
        # Генерируем домашнее задание
        homework_text = await openai_client.generate_homework(
            current_topic={
                "title": str(current_topic.title),
                "description": str(current_topic.description),
                "tasks": json.loads(str(current_topic.tasks))
            },
            conversation_history=conversation_history
        )
        
        # Сохраняем домашнее задание в БД
        await save_homework(
            session=session,
            user_id=user_id,
            topic_id=current_topic.id,
            homework_text=homework_text
        )
        
        # Получаем текущий прогресс пользователя
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if user and user.id:
            # Отмечаем тему как пройденную
            progress_str = str(user.progress) if user.progress else "[]"
            completed_topics = json.loads(progress_str)
            completed_topics.append(current_topic.id)
            new_progress = json.dumps(completed_topics)
            
            # Обновляем пользователя
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    progress=new_progress,
                    current_topic_id=None
                )
            )
        
        await session.commit()
        
        # Отправляем домашнее задание пользователю
        homework_message = homework_assigned_text.format(homework_text=homework_text)
        await message.answer(homework_message)
        
        # Получаем диалоги урока для отправки в группу
        lesson_dialogs = await get_lesson_dialogs(session, user_id, limit=20)
        
        # Отправляем сводку урока в группу
        await send_lesson_summary_to_group(
            bot=message.bot,
            user_id=user_id,
            user_name=message.from_user.full_name,
            lesson_dialogs=lesson_dialogs,
            homework_text=homework_text
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        print(f"Ошибка при выдаче домашнего задания: {e}")
        await message.answer("Извините, произошла ошибка при выдаче домашнего задания.")

@router_user_private.message(Command("test_scheduler"))
async def cmd_test_scheduler(message: Message):
    """
    Тестирование планировщика
    """
    try:
        # Импортируем планировщик
        from app import lesson_scheduler
        
        if lesson_scheduler:
            await lesson_scheduler.send_test_message(message.from_user.id)
            await message.answer("✅ Тестовое сообщение от планировщика отправлено!")
        else:
            await message.answer("❌ Планировщик не запущен")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router_user_private.message(Command("dev_mode"))
async def cmd_dev_mode(message: Message):
    """
    Переключение режима разработки
    """
    try:
        from speech.whisper_engine import DEV_MODE
        
        if DEV_MODE:
            await message.answer(
                "🔧 Текущий режим: РАЗРАБОТКА\n"
                "• Используется заглушка для распознавания речи\n"
                "• OpenAI API не требуется\n"
                "• Подходит для тестирования логики бота\n\n"
                "Для полноценного тестирования:\n"
                "1) Установите OPENAI_API_KEY в .env\n"
                "2) Измените DEV_MODE = False в speech/whisper_engine.py"
            )
        else:
            await message.answer(
                "🚀 Текущий режим: ПРОДАКШЕН\n"
                "• Используется OpenAI Whisper для распознавания речи\n"
                "• Используется OpenAI TTS для генерации речи\n"
                "• Требуется OPENAI_API_KEY\n"
                "• Полноценное тестирование"
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router_user_private.message(Command("status"))
async def cmd_status(message: Message):
    """
    Проверка статуса бота и настроек
    """
    try:
        import os
        from speech.whisper_engine import DEV_MODE
        
        # Проверяем переменные окружения
        token_exists = bool(os.getenv("TOKEN"))
        openai_key_exists = bool(os.getenv("OPENAI_API_KEY"))
        group_id_exists = bool(os.getenv("GROUP_ID"))
        db_url_exists = bool(os.getenv("DB_URL"))
        
        status_text = f"""
🔍 Статус бота:

📱 Telegram Bot: {'✅' if token_exists else '❌'}
🤖 OpenAI API: {'✅' if openai_key_exists else '❌'}
👥 Group ID: {'✅' if group_id_exists else '❌'}
🗄️ Database: {'✅' if db_url_exists else '❌'}

🎤 Режим речи: {'🔧 РАЗРАБОТКА' if DEV_MODE else '🚀 ПРОДАКШЕН'}

"""
        
        if not all([token_exists, openai_key_exists, group_id_exists, db_url_exists]):
            status_text += "\n⚠️ Внимание: Не все переменные окружения настроены!\nСм. SETUP_PRODUCTION.md"
        
        if DEV_MODE:
            status_text += "\n💡 Для продакшена измените DEV_MODE = False"
        else:
            status_text += "\n✅ Бот готов к продакшену!"
        
        await message.answer(status_text)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке статуса: {e}")

@router_user_private.message(F.text)
async def handle_text_message(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик текстовых сообщений (для домашних заданий)
    """
    user_id = message.from_user.id
    text_content = message.text
    
    # Проверяем, есть ли незавершённое домашнее задание
    result = await session.execute(
        select(Homework)
        .where(
            Homework.user_id == user_id,
            Homework.is_checked == False
        )
        .order_by(Homework.date_assigned.desc())
        .limit(1)
    )
    
    homework = result.scalar_one_or_none()
    
    if homework:
        # Получаем информацию о теме для контекста
        topic_result = await session.execute(
            select(Topic).where(Topic.id == homework.topic_id)
        )
        topic = topic_result.scalar_one_or_none()
        topic_title = topic.title if topic else "английскому языку"
        
        # Проверяем домашнее задание через OpenAI
        try:
            homework_check = await openai_client.check_homework(
                homework_text=homework.task_text,
                student_answer=text_content,
                topic_title=topic_title
            )
            
            # Формируем ответ с оценкой
            score = homework_check.get('score', 5)
            feedback = homework_check.get('feedback', 'Спасибо за выполнение домашнего задания!')
            grade_description = homework_check.get('grade_description', 'удовлетворительно')
            
            response_text = f"""
📝 Проверка домашнего задания

🎯 Оценка: {score}/10 ({grade_description})

💬 Обратная связь:
{feedback}

"""
            
            # Добавляем грамматические ошибки, если есть
            grammar_errors = homework_check.get('grammar_errors', [])
            if grammar_errors:
                response_text += f"\n❌ Грамматические ошибки:\n"
                for error in grammar_errors:
                    response_text += f"• {error}\n"
            
            # Добавляем замечания по словарному запасу
            vocabulary_notes = homework_check.get('vocabulary_notes', '')
            if vocabulary_notes:
                response_text += f"\n📚 Словарный запас:\n{vocabulary_notes}\n"
            
            # Добавляем предложения для улучшения
            suggestions = homework_check.get('suggestions', [])
            if suggestions:
                response_text += f"\n💡 Предложения для улучшения:\n"
                for suggestion in suggestions:
                    response_text += f"• {suggestion}\n"
            
            await message.answer(response_text)
            
        except Exception as e:
            print(f"Ошибка при проверке домашнего задания: {e}")
            await message.answer("✅ Спасибо за выполнение домашнего задания! Я проверю его и дам обратную связь.")
        
        # Обновляем ответ на домашнее задание
        updated_homework = await update_homework_answer(
            session=session,
            user_id=user_id,
            answer_text=text_content
        )
        
        if updated_homework:
            # Отправляем ответ на ДЗ в группу
            await send_homework_response_to_group(
                bot=message.bot,
                user_id=user_id,
                user_name=message.from_user.full_name,
                homework_text=updated_homework.task_text,
                user_answer=text_content
            )
        
        await state.clear()  # Очищаем состояние
    else:
        await message.answer("🎤 Отправьте голосовое сообщение, чтобы начать урок!") 