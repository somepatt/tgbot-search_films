import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv
from database import init_db, add_search_history, get_search_history, update_movie_stats, get_user_stats
from movie_search import MovieSearcher
import logging
from datetime import datetime
import json
import random


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'bot_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=".env", override=True)


bot = Bot(token=os.environ['TELEGRAM_TOKEN_NEW'])
dp = Dispatcher()

movie_searcher = MovieSearcher()

# Dictionary to store movie data temporarily
movie_cache = {}

# Dictionary to store game data
game_cache = {}


@dp.message(Command("start"))
async def cmd_start(message: Message):
    logger.info(f"User {message.from_user.id} started the bot")
    await message.answer(
        "Привет! Я бот для поиска фильмов. 🎬\n\n"
        "Просто напиши название фильма, и я найду информацию о нем!\n"
        "Также доступны команды:\n"
        "/help - показать справку\n"
        "/history - история поиска\n"
        "/stats - статистика просмотров\n"
        "/game - сыграть в игру 'Угадай фильм'"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    logger.info(f"User {message.from_user.id} requested help")
    await message.answer(
        "Я умею искать фильмы! 🎥\n\n"
        "Просто напиши название фильма, и я найду информацию о нем.\n"
        "Я покажу:\n"
        "• Название и описание\n"
        "• Рейтинг\n"
        "• Постер\n"
        "• Жанры и страны\n"
        "• Длительность\n"
        "• Ссылки для просмотра\n\n"
        "Команды:\n"
        "/start - начать работу\n"
        "/help - показать это сообщение\n"
        "/history - история поиска\n"
        "/stats - статистика просмотров\n"
        "/game - сыграть в игру 'Угадай фильм'"
    )


@dp.message(Command("history"))
async def cmd_history(message: Message):
    logger.info(f"User {message.from_user.id} requested search history")
    history = await get_search_history(message.from_user.id)
    if not history:
        logger.info(f"No search history found for user {message.from_user.id}")
        await message.answer("У вас пока нет истории поиска.")
        return

    response = "📜 Ваша история поиска:\n\n"
    for item in history:
        response += f"• {item.movie_title}\n"
        response += f"  Поисковый запрос: {item.query}\n"
        response += f"  Дата: {item.timestamp.strftime('%d.%m.%Y %H:%M')}\n\n"

    await message.answer(response)
    logger.info(f"Sent search history to user {message.from_user.id}")


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    logger.info(f"User {message.from_user.id} requested viewing stats")
    stats = await get_user_stats(message.from_user.id)
    if not stats:
        logger.info(f"No viewing stats found for user {message.from_user.id}")
        await message.answer("У вас пока нет статистики просмотров.")
        return

    response = "📊 Ваша статистика просмотров:\n\n"
    for stat in stats:
        response += f"• {stat.movie_title}\n"
        response += f"  Показано раз: {stat.times_shown}\n\n"

    await message.answer(response)
    logger.info(f"Sent viewing stats to user {message.from_user.id}")


@dp.message(Command("game"))
async def cmd_game(message: Message):
    user_id = message.from_user.id
    logger.info(f"User {user_id} started the game")

    try:
        # Инициализируем/сбрасываем кэш для новой игры
        game_cache[user_id] = {
            'score': 0,
            'total_questions': 0
        }

        # Получаем новый вопрос
        text, keyboard = await prepare_new_question(user_id)

        if not keyboard:
            await message.answer(text)
            return

        # Отправляем или редактируем сообщение
        if message.chat.type == 'private':
            await message.answer(text, reply_markup=keyboard)
        else:
            # Для групповых чатов сначала отправляем сообщение
            await message.answer("🎮 Новая игра началась!")
            sent_msg = await message.answer(text, reply_markup=keyboard)
            # Сохраняем ID последнего игрового сообщения
            game_cache[user_id]['last_message_id'] = sent_msg.message_id

    except Exception as e:
        logger.error(f"Error in cmd_game: {str(e)}", exc_info=True)
        await message.answer("😔 Произошла ошибка при запуске игры. Попробуйте позже.")


@dp.message(Command("random"))
async def cmd_random(message: Message):
    logger.info(f"User {message.from_user.id} requested random movie")
    searching_msg = await message.answer("🔍 Ищу случайный фильм из топ-250...")

    try:
        movies = await movie_searcher.random_movie()
        if not movies:
            logger.info(f"No random movies found")
            await searching_msg.edit_text("😕 К сожалению, я не смог найти случайный фильм. Попробуйте позже.")
            return

        movie = movies[0]
        await update_movie_stats(message.from_user.id, movie.movie_id, movie.title)

        response = f"🎬 {movie.title}\n\n"
        response += f"📝 {movie.overview}\n\n"
        response += f"⭐ Рейтинг: {movie.rating}/10\n"
        response += f"📅 Год выпуска: {movie.release_date}\n"
        response += f"⏱ Длительность: {movie.film_length}\n\n"

        if movie.genres:
            response += f"🎭 Жанры: {', '.join(movie.genres)}\n"
        if movie.countries:
            response += f"🌍 Страны: {', '.join(movie.countries)}\n\n"

        response += "🔗 Ссылки для просмотра:\n"
        for link in movie.viewing_links:
            response += f"• {link}\n"

        # Create button for getting another random movie
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🎲 Другой случайный фильм",
                callback_data="random_movie"
            )
        ]])

        if movie.poster_url:
            await searching_msg.delete()
            await message.answer_photo(
                photo=movie.poster_url,
                caption=response,
                reply_markup=keyboard
            )
        else:
            await searching_msg.edit_text(
                text=response,
                reply_markup=keyboard
            )

        logger.info(f"Sent random movie to user {message.from_user.id}")

    except Exception as e:
        logger.error(
            f"Error processing random movie request: {str(e)}", exc_info=True)
        await searching_msg.edit_text("😔 Произошла ошибка при поиске случайного фильма. Попробуйте позже.")


@dp.callback_query(lambda c: c.data == "random_movie")
async def process_random_callback(callback_query: CallbackQuery):
    try:
        # Отправляем сообщение о поиске
        await callback_query.message.edit_caption(
            caption="🔍 Ищу другой случайный фильм..."
        )

        # Получаем новый случайный фильм
        movies = await movie_searcher.random_movie()
        if not movies:
            await callback_query.message.edit_caption(
                caption="😕 К сожалению, я не смог найти случайный фильм. Попробуйте позже."
            )
            return

        movie = movies[0]
        await update_movie_stats(callback_query.from_user.id, movie.movie_id, movie.title)

        response = f"🎬 {movie.title}\n\n"
        response += f"📝 {movie.overview}\n\n"
        response += f"⭐ Рейтинг: {movie.rating}/10\n"
        response += f"📅 Год выпуска: {movie.release_date}\n"
        response += f"⏱ Длительность: {movie.film_length}\n\n"

        if movie.genres:
            response += f"🎭 Жанры: {', '.join(movie.genres)}\n"
        if movie.countries:
            response += f"🌍 Страны: {', '.join(movie.countries)}\n\n"

        response += "🔗 Ссылки для просмотра:\n"
        for link in movie.viewing_links:
            response += f"• {link}\n"

        # Create button for getting another random movie
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🎲 Другой случайный фильм",
                callback_data="random_movie"
            )
        ]])

        # Update the message with new movie info
        if movie.poster_url:
            await callback_query.message.edit_media(
                media=types.InputMediaPhoto(
                    media=movie.poster_url,
                    caption=response
                ),
                reply_markup=keyboard
            )
        else:
            await callback_query.message.edit_text(
                text=response,
                reply_markup=keyboard
            )

        await callback_query.answer()

    except Exception as e:
        logger.error(
            f"Error processing random movie callback: {str(e)}", exc_info=True)
        await callback_query.answer("Произошла ошибка при поиске случайного фильма")


@dp.callback_query(lambda c: c.data.startswith('movie_'))
async def process_movie_callback(callback_query: CallbackQuery):
    try:
        # Extract movie index from callback data
        movie_index = int(callback_query.data.split('_')[1])
        user_id = callback_query.from_user.id

        # Get movie data from cache
        if user_id not in movie_cache:
            await callback_query.answer("Время ожидания истекло. Пожалуйста, выполните поиск снова.")
            return

        movies = movie_cache[user_id]
        if movie_index >= len(movies):
            await callback_query.answer("Фильм не найден")
            return

        movie = movies[movie_index]
        await update_movie_stats(user_id, movie.movie_id, movie.title)

        response = f"🎬 {movie.title}\n\n"
        response += f"📝 {movie.overview}\n\n"
        response += f"⭐ Рейтинг: {movie.rating}/10\n"
        response += f"📅 Год выпуска: {movie.release_date}\n"
        response += f"⏱ Длительность: {movie.film_length}\n\n"

        if movie.genres:
            response += f"🎭 Жанры: {', '.join(movie.genres)}\n"
        if movie.countries:
            response += f"🌍 Страны: {', '.join(movie.countries)}\n\n"

        response += "🔗 Ссылки для просмотра:\n"
        for link in movie.viewing_links:
            response += f"• {link}\n"

        # Create navigation buttons for adjacent movies
        buttons = []
        nav_buttons = []

        # Add previous movie button if exists
        if movie_index > 0:
            prev_movie = movies[movie_index - 1]
            nav_buttons.append(InlineKeyboardButton(
                text=f"⬅️ {prev_movie.title[:20]}...",
                callback_data=f"movie_{movie_index - 1}"
            ))

        # Add next movie button if exists
        if movie_index < len(movies) - 1:
            next_movie = movies[movie_index + 1]
            nav_buttons.append(InlineKeyboardButton(
                text=f"{next_movie.title[:20]}... ➡️",
                callback_data=f"movie_{movie_index + 1}"
            ))

        if nav_buttons:
            buttons.append(nav_buttons)

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Update the message with new movie info
        if movie.poster_url:
            await callback_query.message.edit_media(
                media=types.InputMediaPhoto(
                    media=movie.poster_url,
                    caption=response
                ),
                reply_markup=keyboard
            )
        else:
            await callback_query.message.edit_text(
                text=response,
                reply_markup=keyboard
            )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}", exc_info=True)
        await callback_query.answer("Произошла ошибка при обработке запроса")


@dp.message()
async def handle_movie_search(message: Message):
    if message.text.startswith('/'):
        return

    logger.info(f"User {message.from_user.id} searching for: {message.text}")
    searching_msg = await message.answer("🔍 Ищу информацию о фильме...")

    try:
        movies = await movie_searcher.search_movie(message.text)
        logger.info(f"Found {len(movies)} movies for query: {message.text}")

        if not movies:
            logger.info(f"No movies found for query: {message.text}")
            await searching_msg.edit_text("😕 К сожалению, я не нашел фильмов по вашему запросу.")
            return

        # Store movies in cache
        movie_cache[message.from_user.id] = movies

        # Get first movie
        movie = movies[0]
        await update_movie_stats(message.from_user.id, movie.movie_id, movie.title)

        # Create response for first movie
        response = f"🎬 {movie.title}\n\n"
        response += f"📝 {movie.overview}\n\n"
        response += f"⭐ Рейтинг: {movie.rating}/10\n"
        response += f"📅 Год выпуска: {movie.release_date}\n"
        response += f"⏱ Длительность: {movie.film_length}\n\n"

        if movie.genres:
            response += f"🎭 Жанры: {', '.join(movie.genres)}\n"
        if movie.countries:
            response += f"🌍 Страны: {', '.join(movie.countries)}\n\n"

        response += "🔗 Ссылки для просмотра:\n"
        for link in movie.viewing_links:
            response += f"• {link}\n"

        # Create navigation buttons for adjacent movies
        buttons = []
        nav_buttons = []

        # Add next movie button if exists
        if len(movies) > 1:
            next_movie = movies[1]
            nav_buttons.append(InlineKeyboardButton(
                text=f"{next_movie.title[:20]}... ➡️",
                callback_data=f"movie_1"
            ))

        if nav_buttons:
            buttons.append(nav_buttons)

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Send first movie with buttons
        if movie.poster_url:
            await searching_msg.delete()
            await message.answer_photo(
                photo=movie.poster_url,
                caption=response,
                reply_markup=keyboard
            )
        else:
            await searching_msg.edit_text(
                text=response,
                reply_markup=keyboard
            )

        logger.info(
            f"Sent first movie with navigation buttons to user {message.from_user.id}")

    except Exception as e:
        logger.error(
            f"Error processing search request: {str(e)}", exc_info=True)
        await searching_msg.edit_text("😔 Произошла ошибка при поиске фильма. Попробуйте позже.")


@dp.callback_query(lambda c: c.data == "next_question")
async def process_next_question(callback_query: CallbackQuery):
    try:
        user_id = callback_query.from_user.id
        logger.info(f"Processing next question for user {user_id}")

        # Подготавливаем новый вопрос
        text, keyboard = await prepare_new_question(user_id)

        # Редактируем текущее сообщение
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()

    except Exception as e:
        logger.error(
            f"Error in process_next_question: {str(e)}", exc_info=True)
        await callback_query.answer("Произошла ошибка при переходе к следующему вопросу")


async def prepare_new_question(user_id: int):
    try:
        # Проверяем, не достигнут ли лимит вопросов
        game_data = game_cache.get(user_id, {'score': 0, 'total_questions': 0})
        if game_data['total_questions'] >= 5:
            # Формируем итоговый результат
            final_score = game_data['score']
            total_questions = game_data['total_questions']
            percentage = (final_score / total_questions) * 100

            result_text = (
                "🎮 Игра окончена!\n\n"
                f"Ваш результат: {final_score} из {total_questions}\n"
                f"Процент правильных ответов: {percentage:.1f}%\n\n"
            )

            # Добавляем оценку результата
            if percentage == 100:
                result_text += "🏆 Отличный результат! Вы настоящий киноман!"
            elif percentage >= 80:
                result_text += "🌟 Отличная работа! Вы хорошо разбираетесь в кино!"
            elif percentage >= 60:
                result_text += "👍 Хороший результат! Есть куда расти!"
            else:
                result_text += "📚 Неплохо! Стоит посмотреть больше фильмов!"

            # Добавляем кнопку для новой игры
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🎮 Начать новую игру",
                    callback_data="new_game"
                )
            ]])

            # Очищаем кэш игры
            if user_id in game_cache:
                del game_cache[user_id]

            return result_text, keyboard

        logger.info("Getting random movies for game...")
        movies = await movie_searcher.get_random_movies_for_game(4)
        if not movies:
            logger.error("No movies found for game")
            return "😕 К сожалению, я не смог подготовить игру. Попробуйте позже.", None

        # Выбираем новый правильный фильм
        correct_movie = random.choice(movies)
        logger.info(f"Selected correct movie: {correct_movie.title}")

        # Обновляем кэш
        game_data.update({
            'correct_movie': correct_movie,
            'options': [m for m in movies if m != correct_movie]
        })
        game_cache[user_id] = game_data

        # Формируем сообщение
        response = (
            "🎮 Угадай фильм!\n\n"
            f"📝 {movie_searcher.get_movie_description_for_game(correct_movie)}\n\n"
            f"Вопрос {game_data['total_questions'] + 1} из 5\n"
            "Выберите правильный ответ:"
        )

        # Создаем кнопки
        all_movies = [correct_movie] + game_data['options']
        random.shuffle(all_movies)
        buttons = [
            [InlineKeyboardButton(
                text=m.title, callback_data=f"game_{m.movie_id}")]
            for m in all_movies
        ]

        return response, InlineKeyboardMarkup(inline_keyboard=buttons)

    except Exception as e:
        logger.error(f"Error preparing new question: {str(e)}", exc_info=True)
        return "😔 Произошла ошибка при подготовке вопроса", None


@dp.callback_query(lambda c: c.data == "new_game")
async def process_new_game(callback_query: CallbackQuery):
    try:
        user_id = callback_query.from_user.id
        logger.info(f"Starting new game for user {user_id}")

        # Инициализируем новый кэш игры
        game_cache[user_id] = {
            'score': 0,
            'total_questions': 0
        }

        # Подготавливаем первый вопрос
        text, keyboard = await prepare_new_question(user_id)

        # Редактируем сообщение с новым вопросом
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()

    except Exception as e:
        logger.error(f"Error starting new game: {str(e)}", exc_info=True)
        await callback_query.answer("Произошла ошибка при запуске новой игры")


@dp.callback_query(lambda c: c.data.startswith('game_'))
async def process_game_callback(callback_query: CallbackQuery):
    try:
        user_id = callback_query.from_user.id
        logger.info(f"Processing game callback for user {user_id}")

        # Проверка наличия активной игры
        game_data = game_cache.get(user_id)
        if not game_data or 'correct_movie' not in game_data:
            await callback_query.answer("Игра закончилась. Начните новую игру командой /game")
            return

        # Определение выбранного и правильного ответов
        selected_movie_id = callback_query.data.split('_')[1]
        correct_movie = game_data['correct_movie']
        is_correct = selected_movie_id == correct_movie.movie_id

        # Обновление статистики
        game_data['total_questions'] += 1
        if is_correct:
            game_data['score'] += 1

        # Формирование результата
        result_text = ("✅ Правильно!" if is_correct
                       else f"❌ Неправильно! Правильный ответ: {correct_movie.title}")

        # Удаление правильного ответа из кэша
        del game_data['correct_movie']

        # Редактирование сообщения с результатом
        await callback_query.message.edit_text(
            f"{result_text}\n\n"
            f"Ваш счет: {game_data['score']}/{game_data['total_questions']}\n\n"
            "Нажмите кнопку ниже, чтобы продолжить игру:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🎮 Следующий вопрос",
                    callback_data="next_question"
                )
            ]])
        )
        await callback_query.answer()

    except Exception as e:
        logger.error(
            f"Error processing game callback: {str(e)}", exc_info=True)
        await callback_query.answer("Произошла ошибка при обработке ответа")


async def main():
    await init_db()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
