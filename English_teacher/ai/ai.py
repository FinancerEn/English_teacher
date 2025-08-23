import aiohttp
import json
import os
import logging
import random
import tempfile
import asyncio
import random
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Настройка логгера
logger = logging.getLogger(__name__)

class OpenAIClient:
    """
    Клиент для работы с OpenAI API (GPT-4, Whisper, TTS).
    """
    
    def __init__(self):
        # Основные переменные для OpenAI
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        # Проверяем наличие обязательных переменных
        if not self.api_key:
            logger.warning("OPENAI_API_KEY не найден в переменных окружения! Будет использован режим тестирования.")
        
        # Инициализируем OpenAI клиент
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None


    async def generate_intelligent_response(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, str]], 
        current_topic: Optional[Dict] = None
    ) -> tuple[str, Dict]:
        """
        Это метод, который решает проблему рассинхрона 2 сообщений ассистента (1е и совет)
        Сначала проверяет ответ ученика, потом генерирует согласованный ответ с учетом проверки
        
        Returns:
            tuple: (ответ_бота, результат_проверки)
        """
        
        # Сначала проверяем ответ пользователя
        feedback_result = await self.check_pronunciation_and_answer(
            user_answer=user_message,
            current_topic=current_topic,
            context="Intelligent response generation",
            conversation_history=conversation_history
        )
        
        # Генерируем согласованный ответ(2а сообщения ассистента 1е и совет) на основе проверки
        ai_response = await self.send_message_with_feedback(
            user_message=user_message,
            conversation_history=conversation_history,
            current_topic=current_topic,
            feedback_result=feedback_result
        )
        
        return ai_response, feedback_result


    async def send_message_with_feedback(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, str]], 
        current_topic: Optional[Dict] = None,
        feedback_result: Optional[Dict] = None
    ) -> str:
        """
        Отправляет сообщение с учётом синхронизации 2 сообщений ассистента (1е и совет)
        """
        
        # Проверяем, доступен ли OpenAI API
        if not self.api_key or self.api_key == "your_openai_api_key":
            # Режим тестирования без API
            logger.warning(f"Fallback режим: api_key={bool(self.api_key)}")
            return self._get_test_response(user_message, current_topic)
        
        logger.info(f"Используем OpenAI API: api_key={self.api_key[:10]}...")
        
        # Формируем системный промпт с учётом результата проверки
        system_prompt = self.create_system_prompt_with_feedback(current_topic, feedback_result)
        
        # Формируем сообщения для API в формате OpenAI
        messages = [{"role": "system", "content": system_prompt}]
        
        # Добавляем историю диалога
        for msg in conversation_history[-20:]:  # Последние 20 сообщений
            # Конвертируем роль 'bot' в 'assistant' для OpenAI API
            role = "assistant" if msg["role"] == "bot" else msg["role"]
            messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Используем GPT-4o-mini для быстрых ответов
                messages=messages,
                max_tokens=150,  # Ограничиваем длину ответа
                temperature=0.7,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
                        
        except Exception as e:
            logger.error(f"Ошибка при отправке запроса к OpenAI: {e}")
            logger.warning("Переключаемся на fallback режим из-за ошибки API")
            return self._get_test_response(user_message, current_topic)

    async def send_message(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, str]], 
        current_topic: Optional[Dict] = None,
        feedback_result: Optional[Dict] = None
    ) -> str:
        """
        Отправляет сообщение в OpenAI GPT и получает ответ.
        
        Args:
            user_message: Сообщение пользователя
            conversation_history: История диалога (последние 20 сообщений)
            current_topic: Текущая тема урока
            
        Returns:
            Ответ от OpenAI GPT
        """
        
        # Проверяем, доступен ли OpenAI API
        if not self.api_key or self.api_key == "your_openai_api_key":
            # Режим тестирования без API
            logger.warning(f"Fallback режим: api_key={bool(self.api_key)}")
            return self._get_test_response(user_message, current_topic)
        
        logger.info(f"Используем OpenAI API: api_key={self.api_key[:10]}...")
        
        # Определяем тип ответа на основе наличия темы
        if current_topic is None:
            # Режим общения с учителем - отвечаем на вопросы по английскому
            return await self._send_teacher_message(user_message, conversation_history)
        else:
            # Режим урока - отвечаем в контексте темы
            return await self._send_lesson_message(user_message, conversation_history, current_topic)

    async def _send_teacher_message(self, user_message: str, conversation_history: List[Dict[str, str]]) -> str:
        """
        Отправляет сообщение в режиме общения с учителем
        
        Args:
            user_message: Сообщение пользователя
            conversation_history: История диалога
            
        Returns:
            Ответ от учителя на английском языке
        """
        system_prompt = """
        Ты - дружелюбный учитель английского языка Marcus. Отвечай на вопросы ученика по английскому языку.
        
        Твоя задача:
        - Отвечать на любые вопросы по английскому языку (грамматика, произношение, значения слов, идиомы и т.д.)
        - Объяснять понятно и доступно
        - Давать примеры использования
        - Быть дружелюбным и поддерживающим
        - Отвечать на английском языке с русским переводом в скобках
        - Использовать эмодзи для живости
        
        Формат ответа:
        Английский ответ "Русский перевод в скобках"
        """
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Добавляем историю диалога
        for msg in conversation_history[-10:]:  # Последние 10 сообщений
            role = "assistant" if msg["role"] == "bot" else msg["role"]
            messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=200,
                temperature=0.7,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения учителю: {e}")
            return "I'm sorry, there was an error. Please try again later. (Извините, произошла ошибка. Попробуйте позже.)"

    async def _send_lesson_message(self, user_message: str, conversation_history: List[Dict[str, str]], current_topic: Dict[str, Any]) -> str:
        """
        Отправляет сообщение в режиме урока
        
        Args:
            user_message: Сообщение пользователя
            conversation_history: История диалога
            current_topic: Текущая тема урока
            
        Returns:
            Ответ от учителя в контексте урока
        """
        # Используем существующую логику для уроков
        system_prompt = self.create_system_prompt(current_topic, None)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Добавляем историю диалога
        for msg in conversation_history[-20:]:
            role = "assistant" if msg["role"] == "bot" else msg["role"]
            messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения урока: {e}")
            return self._get_test_response(user_message, current_topic)


    async def transcribe_audio(self, audio_path: str) -> str:
        """
        Транскрибирует аудио файл в текст с помощью OpenAI Whisper.
        
        Args:
            audio_path: Путь к аудио файлу
            
        Returns:
            Транскрибированный текст
        """
        
        # Проверяем, доступен ли OpenAI API
        if not self.api_key or self.api_key == "your_openai_api_key":
            # Режим тестирования без API
            logger.warning("Fallback режим для транскрибации")
            return "Hello, teacher! I am ready for the English lesson."
        
        try:
            with open(audio_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"  # Указываем английский язык
                )
            
            transcribed_text = response.text.strip()
            logger.info(f"Транскрибированный текст: '{transcribed_text}'")
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Ошибка при транскрибации: {e}")
            return "Hello, teacher! I am ready for the English lesson."

    async def generate_speech(self, text: str) -> bytes:
        """
        Генерирует речь из текста с помощью OpenAI TTS.
        
        Args:
            text: Текст для озвучивания
            
        Returns:
            Байты аудио файла
        """
        
        # Проверяем, доступен ли OpenAI API
        if not self.api_key or self.api_key == "your_openai_api_key":
            # Режим тестирования без API
            logger.warning("Fallback режим для TTS")
            return b""  # Пустые байты для fallback
        
        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice="onyx",  # Используем мужской басовый голос "onyx" для учителя Marcus
                input=text
            )
            
            audio_bytes = response.content
            logger.info(f"Сгенерирована речь для текста: '{text[:50]}...'")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Ошибка при генерации речи: {e}")
            return b""  # Пустые байты для fallback
    


    
    async def check_pronunciation_and_answer(
        self, 
        user_answer: str, 
        current_topic: Optional[Dict] = None,
        context: str = "",
        conversation_history: Optional[list] = None
    ) -> Dict:
        """
        Проверяет произношение и правильность ответа пользователя.
        
        Args:
            user_answer: Ответ пользователя
            expected_answer: Ожидаемый правильный ответ
            context: Контекст вопроса
            
        Returns:
            Dict с результатом проверки и обратной связью
        """
        
        # Проверяем, доступен ли OpenAI API
        if not self.api_key or self.api_key == "your_openai_api_key":
            # Fallback режим - простая проверка
            # Сначала определяем ожидаемый ответ, как в обычном режиме
            if current_topic:
                topic_tasks = current_topic.get('tasks', [])
                if isinstance(topic_tasks, str):
                    try:
                        topic_tasks = json.loads(topic_tasks)
                    except:
                        topic_tasks = []
                
                # Генерируем ожидаемый ответ на основе задач темы
                if topic_tasks and len(topic_tasks) > 0:
                    expected_answer = topic_tasks[0]  # Берём первую задачу как пример
                else:
                    expected_answer = f"Answer about {current_topic.get('title', 'английскому языку')}"
            else:
                expected_answer = "Hello, my name is [name]. I like [hobby]."
            
            return self._simple_answer_check(user_answer, expected_answer, current_topic.get('title', 'английскому языку') if current_topic else 'английскому языку', "")
        
        # Генерируем контекст на основе текущей темы
        topic_title = current_topic.get('title', 'английскому языку') if current_topic else 'английскому языку'
        topic_description = current_topic.get('description', '') if current_topic else ''
        
        # Анализируем контекст диалога
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            # Берём последние 3 сообщения для понимания контекста
            recent_messages = conversation_history[-3:]
            conversation_context = " ".join([msg.get('content', '') for msg in recent_messages])
        
        # Определяем ожидаемый ответ на основе контекста диалога
        if conversation_context:
            # Если есть контекст диалога, используем его для определения ожидаемого ответа
            expected_answer = f"Answer based on the conversation context: {conversation_context[:100]}..."
        elif current_topic:
            topic_tasks = current_topic.get('tasks', [])
            if isinstance(topic_tasks, str):
                try:
                    topic_tasks = json.loads(topic_tasks)
                except:
                    topic_tasks = []
            
            # Генерируем ожидаемый ответ на основе задач темы
            if topic_tasks and len(topic_tasks) > 0:
                expected_answer = topic_tasks[0]  # Берём первую задачу как пример
            else:
                expected_answer = f"Answer about {topic_title}"
        else:
            expected_answer = "Hello, my name is [name]. I like [hobby]."
        
        system_prompt = f"""
        Ты - учитель английского языка Marcus. Проверяй ответы ученика по теме "{topic_title}" и давай обратную связь на РУССКОМ языке.
        
        Тема урока: {topic_title}
        Описание темы: {topic_description}
        Контекст диалога: {conversation_context}
        
        Правила проверки:
        1. Учитывай возможные ошибки транскрибации (yoy вместо you, dont вместо don't и т.д.)
        2. Анализируй ответ в контексте текущего диалога, а не по шаблону
        3. Если ответ логично продолжает разговор - хвали ученика
        4. Если есть ошибки - объясни их на русском языке
        5. Покажи правильный вариант на Английском языке
        6. Будь дружелюбной и поддерживающей
        7. Отвечай кратко (1-2 предложения)
        8. НЕ давай советы по темам, которые не обсуждаются в диалоге
        
        ВАЖНО: Оценивай ответ ученика по тому, насколько он соответствует контексту разговора, а не по жёстким шаблонам.
        
        Формат ответа (строго JSON):
        {{
            "is_correct": true/false,
            "feedback": "Обратная связь на русском языке",
            "correct_answer": "Правильный ответ на Английском языке",
            "explanation": "Объяснение ошибок (если есть)"
        }}
        """
        
        user_prompt = f"""
        Тема урока: {topic_title}
        Контекст диалога: {conversation_context}
        Ответ ученика: "{user_answer}"
        Дополнительный контекст: "{context}"
        
        Проверь ответ ученика в контексте текущего диалога. Оцени, насколько ответ логично продолжает разговор и соответствует обсуждаемой теме.
        
        ВАЖНО: Не используй жёсткие шаблоны. Оценивай ответ по его уместности в контексте разговора.
        
        Дай обратную связь в формате JSON.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=200,
                temperature=0.3,  # Более консистентные ответы
                timeout=30
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Пытаемся распарсить JSON ответ
            try:
                result = json.loads(response_text)
                return result
            except:
                # Если не удалось распарсить JSON, используем простую проверку
                return self._simple_answer_check(user_answer, expected_answer, topic_title, conversation_context)
                
        except Exception as e:
            logger.error(f"Ошибка при проверке ответа: {e}")
            return self._simple_answer_check(user_answer, expected_answer, topic_title, conversation_context)

    def _get_test_response(self, user_message: str, current_topic: Optional[Dict] = None) -> str:
        """
        Возвращает сообщение об ошибке OpenAI API
        """
        logger.error("OpenAI API недоступен - возвращаем сообщение об ошибке")
        return "❌ Проблемы с доступом к OpenAI API. Пожалуйста, попробуйте позже или обратитесь к администратору."


    def create_system_prompt(self, current_topic: Optional[Dict] = None, feedback_result: Optional[Dict] = None) -> str:
        """
        Создаёт системный промпт для OpenAI GPT.
        
        Args:
            current_topic: Информация о текущей теме
            
        Returns:
            Системный промпт
        """
        
        base_prompt = """
        Ты - личный учитель английского языка Marcus. Ты грамотный, поддерживающий и терпеливый.
        
        ВАЖНО: Ты ОБЯЗАТЕЛЬНО должен отвечать на АНГЛИЙСКОМ языке!
        
        Правила ответов:
        1. ВСЕГДА отвечай на АНГЛИЙСКОМ языке
        2. Используй простые конструкции, подходящие для школьного уровня
        3. Если ученик говорит на русском - переводи его на английский и исправляй ошибки
        4. Задавай вопросы на английском
        5. Будь грамотным и серьёзным
        6. Фокусируйся на обучении и задавай вопросы для практики
        7. Используй эмодзи для создания дружелюбной атмосферы
        8. Давай советы по произношению и грамматике
        9. ВАЖНО: Если есть результат проверки ответа ученика - учитывай его в своём ответе
        
        КРИТИЧНО: Отвечай КОРОТКО! Максимум 2-3 предложения, не больше!
        
        Примеры правильных ответов:
        "Hello! 👋 My name is Marcus. What do you like to do? Maybe reading, music, or sports? Tell me about it! You can send me a voice message!"
        "That sounds interesting! 🌟 What kind of music do you make? And what do you enjoy most about programming?"
        "That is a great idea! Teaching English can be fun. What age is your sister? What topics do you want to start with?"
        """
        
        if current_topic:
            topic_prompt = f"""
            
            Текущая тема: {current_topic.get('title', 'Неизвестная тема')}
            Описание: {current_topic.get('description', '')}
            Задания: {current_topic.get('tasks', [])}
            
            Сосредоточься на этой теме и используй соответствующий словарь.
            """
            base_prompt += topic_prompt
        
        return base_prompt

    def create_system_prompt_with_feedback(self, current_topic: Optional[Dict] = None, feedback_result: Optional[Dict] = None) -> str:
        """
        Создаёт системный промпт для ответа с учётом синхронизации 2 сообщений ассистента
        (1е и совет). Это ключ к решению проблемы рассинхрона! 
        Была проблема когда ассистент отвечал на вопросы не согласованно с проверкой.
        """
        
        base_prompt = """
        Ты - личный учитель английского языка Marcus. Ты грамотный, поддерживающий и терпеливый.
        
        ВАЖНО: Ты ОБЯЗАТЕЛЬНО должен отвечать на АНГЛИЙСКОМ языке!
        
        Правила ответов:
        1. ВСЕГДА отвечай на АНГЛИЙСКОМ языке
        2. Используй простые конструкции, подходящие для школьного уровня
        3. Если ученик говорит на русском - переводи его на английский и исправляй ошибки
        4. Задавай вопросы на английском
        5. Будь грамотным и серьёзным
        6. Фокусируйся на обучении и задавай вопросы для практики
        7. Используй эмодзи для создания дружелюбной атмосферы
        8. Давай советы по произношению и грамматике
        
        КРИТИЧНО: Отвечай КОРОТКО! Максимум 2-3 предложения, не больше!
        """
        
        if feedback_result:
            # Добавляем информацию о результате проверки
            is_correct = feedback_result.get('is_correct', True)
            correct_answer = feedback_result.get('correct_answer', '')
            explanation = feedback_result.get('explanation', '')
            
            feedback_prompt = f"""
            
            РЕЗУЛЬТАТ ПРОВЕРКИ ОТВЕТА УЧЕНИКА:
            - Ответ правильный: {is_correct}
            - Правильный вариант: {correct_answer}
            - Объяснение: {explanation}
            
            ВАЖНО: Твой ответ должен быть согласован с результатом проверки!
            Если ответ ученика правильный - хвали его и задавай следующий вопрос.
            Если есть ошибки - мягко исправь их и задавай вопрос по той же теме.
            НЕ задавай вопросы по другим темам, если ученик отвечает на текущую тему!
            """
            base_prompt += feedback_prompt
        
        if current_topic:
            topic_prompt = f"""
            
            Текущая тема: {current_topic.get('title', 'Неизвестная тема')}
            Описание: {current_topic.get('description', '')}
            Задания: {current_topic.get('tasks', [])}
            
            Сосредоточься на этой теме и используй соответствующий словарь.
            """
            base_prompt += topic_prompt
        
        return base_prompt
    
    async def generate_homework(
        self, current_topic: Dict, conversation_history: List[Dict[str, str]]) -> str:
        """
        Генерирует домашнее задание на основе текущей темы и диалога.
        
        Args:
            current_topic: Текущая тема
            conversation_history: История диалога
            
        Returns:
            Текст домашнего задания
        """
        
        # Проверяем, доступен ли OpenAI API
        if not self.api_key or self.api_key == "your_openai_api_key":
            # Режим тестирования без API
            logger.warning(f"Fallback режим для домашнего задания: api_key={bool(self.api_key)}")
            return self._get_test_homework(current_topic)
        
        logger.info(f"Используем OpenAI API для домашнего задания: api_key={self.api_key[:10]}...")
        
        system_prompt = f"""
        Ты - учитель английского языка. Создай домашнее задание для ученика.
        
        Тема: {current_topic.get('title', '')}
        Описание: {current_topic.get('description', '')}
        
        Правила для домашнего задания:
        1. Задание должно быть связано с пройденной темой
        2. Используй простые конструкции
        3. Задание должно быть выполнимым за 10-15 минут
        4. Напиши задание на русском языке
        5. Укажи, что ученик должен ответить текстом
        """
        
        # Анализируем диалог для персонализации задания
        user_responses = [msg["content"] for msg in conversation_history if msg["role"] == "user"]
        recent_responses = user_responses[-5:] if len(user_responses) >= 5 else user_responses
        
        context = f"""
        Последние ответы ученика: {'; '.join(recent_responses)}
        
        Создай домашнее задание, учитывая уровень ученика и пройденный материал.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=300,
                temperature=0.7,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
                        
        except Exception as e:
            logger.error(f"Ошибка при генерации домашнего задания: {e}")
            logger.warning("Переключаемся на fallback режим для домашнего задания из-за ошибки API")
            return self._get_test_homework(current_topic)
    
    def _get_test_homework(self, current_topic: Dict) -> str:
        """
        Возвращает сообщение об ошибке OpenAI API для домашнего задания
        """
        logger.error("OpenAI API недоступен для генерации домашнего задания")
        return "❌ Проблемы с доступом к OpenAI API. Домашнее задание не может быть сгенерировано. Пожалуйста, попробуйте позже."
    
    def _simple_answer_check(self, user_answer: str, expected_answer: str, topic_title: str = "английскому языку", conversation_context: str = "") -> Dict:
        """
        Простая проверка ответа для fallback режима
        """
        # Нормализуем ответы для сравнения
        user_clean = self._normalize_answer(user_answer)
        expected_clean = self._normalize_answer(expected_answer)
        
        # Проверяем похожесть
        similarity = self._calculate_similarity(user_clean, expected_clean)
        
        # Если есть контекст диалога, даём более мягкую оценку
        if conversation_context:
            if similarity >= 0.5:  # Снижаем порог для контекстных ответов
                return {
                    "is_correct": True,
                    "feedback": f"Отлично! 👍 Ты хорошо ответил в контексте разговора!",
                    "correct_answer": user_answer,  # Используем ответ ученика как правильный
                    "explanation": ""
                }
            else:
                return {
                    "is_correct": False,
                    "feedback": f"Почти правильно! Попробуй ответить более подробно.",
                    "correct_answer": user_answer,
                    "explanation": "Твой ответ понятен, но можно добавить больше деталей."
                }
        else:
            # Стандартная проверка без контекста
            if similarity >= 0.7:
                return {
                    "is_correct": True,
                    "feedback": f"Отлично! 👍 Ты хорошо ответил по теме '{topic_title}'!",
                    "correct_answer": expected_answer,
                    "explanation": ""
                }
            else:
                return {
                    "is_correct": False,
                    "feedback": f"Почти правильно! По теме '{topic_title}' правильный ответ: '{expected_answer}'",
                    "correct_answer": expected_answer,
                    "explanation": f"Попробуй еще раз, учитывая тему '{topic_title}'!"
                }
    
    def _normalize_answer(self, answer: str) -> str:
        """
        Нормализует ответ для сравнения
        """
        # Приводим к нижнему регистру
        answer = answer.lower()
        
        # Убираем лишние пробелы
        answer = " ".join(answer.split())
        
        # Исправляем частые ошибки транскрибации
        corrections = {
            "yoy": "you",
            "dont": "don't",
            "cant": "can't",
            "wont": "won't",
            "im": "i'm",
            "ive": "i've",
            "youre": "you're",
            "theyre": "they're",
            "were": "we're"
        }
        
        for wrong, correct in corrections.items():
            answer = answer.replace(wrong, correct)
        
        return answer
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Простой расчет похожести текстов
        """
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)

    async def check_homework(self, homework_text: str, student_answer: str, topic_title: str) -> Dict:
        """
        Проверяет домашнее задание и даёт оценку по 10-балльной шкале
        
        Args:
            homework_text: Текст домашнего задания
            student_answer: Ответ ученика
            topic_title: Название темы
            
        Returns:
            Словарь с результатами проверки
        """
        system_prompt = f"""
        Ты - опытный учитель английского языка Marcus. Твоя задача - проверить домашнее задание ученика и дать подробную обратную связь.
        
        Критерии оценки (по 10-балльной шкале):
        - 9-10: Отличная работа, правильная грамматика, богатый словарный запас
        - 7-8: Хорошая работа, небольшие ошибки, понятная речь
        - 5-6: Удовлетворительно, есть ошибки, но основная мысль понятна
        - 3-4: Неудовлетворительно, много ошибок, сложно понять
        - 1-2: Очень плохо, много грубых ошибок
        
        Ответь в формате JSON:
        {{
            "score": число от 1 до 10,
            "feedback": "Подробная обратная связь на русском языке",
            "grammar_errors": ["список грамматических ошибок"],
            "vocabulary_notes": "замечания по словарному запасу",
            "suggestions": ["список предложений для улучшения"],
            "grade_description": "описание оценки (отлично/хорошо/удовлетворительно/неудовлетворительно)"
        }}
        """
        
        user_prompt = f"""
        Тема урока: {topic_title}
        
        Домашнее задание:
        {homework_text}
        
        Ответ ученика:
        {student_answer}
        
        Проверь домашнее задание и дай оценку по 10-балльной шкале.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                temperature=0.3,
                timeout=30
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Пытаемся распарсить JSON ответ
            try:
                result = json.loads(response_text)
                return result
            except:
                # Если не удалось распарсить JSON, используем простую проверку
                return self._simple_answer_check(homework_text, student_answer)
                
        except Exception as e:
            logger.error(f"Ошибка при проверке домашнего задания: {e}")
            return self._simple_answer_check(homework_text, student_answer)


    async def generate_lesson_start_message(self, topic_title: str, topic_description: str) -> str:
        """
        Генерирует сообщение для начала урока
        
        Args:
            topic_title: Название темы
            topic_description: Описание темы
            
        Returns:
            Текст сообщения для начала урока
        """
        system_prompt = """
        Ты - дружелюбный учитель английского языка Marcus. Создай приветственное сообщение для начала урока.
        
        Сообщение должно быть:
        - Мотивирующим и дружелюбным
        - На английском языке с русским переводом
        - Интересным и привлекающим внимание
        - Коротким (2-3 предложения)
        - С эмодзи для живости
        
        Формат:
        Английский текст "Русский перевод в скобках"
        """
        
        user_prompt = f"""
        Создай приветственное сообщение для начала урока по теме: "{topic_title}"
        
        Описание темы: {topic_description}
        
        Сообщение должно мотивировать ученика к изучению английского языка.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации сообщения начала урока: {e}")
            return f"Hello! 👋 Ready to learn about {topic_title}? Let's start our English lesson! (Привет! Готов изучать тему '{topic_title}'? Начинаем урок английского!)"

    async def generate_lesson_task(self, topic_title: str, topic_description: str, topic_tasks: list) -> str:
        """
        Генерирует простое задание для начала урока
        
        Args:
            topic_title: Название темы
            topic_description: Описание темы
            topic_tasks: Список задач по теме
            
        Returns:
            Текст простого задания для урока
        """
        system_prompt = """
        Ты - опытный учитель английского языка Marcus. Создай ПРОСТОЕ задание для ученика по теме урока.
        
        ВАЖНО: Это НЕ домашнее задание! Это простое задание для начала урока.
        
        Задание должно быть:
        - ОЧЕНЬ ПРОСТЫМ (максимум 1-2 предложения в ответе)
        - Конкретным и понятным
        - На АНГЛИЙСКОМ языке
        - Соответствующим теме урока
        - Выполнимым за 30 секунд
        - Как простой вопрос в диалоге
        
        Формат: Один простой вопрос на английском языке
        Примеры ПРАВИЛЬНЫХ заданий:
        - "Tell me about your best friend in two words"
        - "What do you like to do?"
        - "Describe your day in one sentence"
        - "What's your favorite hobby?"
        
        НЕ ДЕЛАЙ сложные задания типа:
        - "Describe in 5-7 sentences..."
        - "Use at least 3 adjectives..."
        - "Write an essay about..."
        """
        
        user_prompt = f"""
        Создай ПРОСТОЕ задание для ученика по теме: "{topic_title}"
        
        Описание темы: {topic_description}
        Доступные задачи: {', '.join(topic_tasks) if isinstance(topic_tasks, list) else topic_tasks}
        
        ВАЖНО: Это задание для начала урока, а не домашнее задание!
        Задание должно быть очень простым - ученик должен ответить максимум 1-2 предложениями.
        Сделай это как простой вопрос в диалоге, а не как сложную задачу.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=50,  # Уменьшаем для более коротких заданий
                temperature=0.7,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации задания урока: {e}")
            # Fallback задание - простое
            if isinstance(topic_tasks, list) and len(topic_tasks) > 0:
                # Берем первое задание, но делаем его проще
                task = topic_tasks[0]
                if "предложениях" in task or "предложения" in task:
                    return task.replace("в двух предложениях", "в одном предложении").replace("в нескольких предложениях", "в одном предложении")
                return task
            else:
                return f"Расскажи о себе в одном предложении"


    async def generate_lesson_end_message(self, conversation_summary: str, user_name: str) -> str:
        """
        Генерирует персонализированное сообщение при завершении урока
        
        Args:
            conversation_summary: Краткое описание урока
            user_name: Имя пользователя
            
        Returns:
            Персонализированное сообщение завершения
        """
        system_prompt = """
        Ты - заботливый учитель английского языка Marcus. Создай персонализированное сообщение для завершения урока.
        
        Сообщение должно быть:
        - Поддерживающим и мотивирующим
        - Персонализированным под ученика
        - На русском языке
        - Коротким (2-3 предложения)
        - С эмодзи для дружелюбности
        
        Тон: дружелюбный, поддерживающий, мотивирующий
        """
        
        user_prompt = f"""
        Создай персонализированное сообщение для завершения урока.
        
        Имя ученика: {user_name}
        Краткое описание урока: {conversation_summary}
        
        Сообщение должно поддержать ученика и мотивировать его продолжать изучение английского.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=100,
                temperature=0.7,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации сообщения завершения урока: {e}")
            return f"Привет, {user_name}! Ты хорошо поработал на уроке! Продолжай практиковаться, и ты станешь еще лучше. У тебя есть много потенциала! 😊"


# Создаём глобальный экземпляр клиента
openai_client = OpenAIClient() 