import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from database import init_db, add_search_history, get_search_history, update_movie_stats, get_user_stats
from movie_search import MovieSearcher
import logging
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'bot_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

bot = Bot(token=os.environ['TELEGRAM_TOKEN_NEW'])
dp = Dispatcher()

movie_searcher = MovieSearcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    logger.info(f"User {message.from_user.id} started the bot")
    await message.answer(
        "Привет! Я бот для поиска фильмов. 🎬\n\n"
        "Просто напиши название фильма, и я найду информацию о нем!\n"
        "Также доступны команды:\n"
        "/help - показать справку\n"
        "/history - история поиска\n"
        "/stats - статистика просмотров"
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
        "/stats - статистика просмотров"
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

        for movie in movies:
            logger.info(f"Processing movie: {movie.title}")
            await update_movie_stats(message.from_user.id, movie.movie_id, movie.title)

            await add_search_history(
                message.from_user.id,
                message.text,
                movie.title,
                movie.movie_id
            )

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

            if movie.poster_url:
                await message.answer_photo(movie.poster_url, caption=response)
                logger.info(f"Sent movie info with poster for: {movie.title}")
            else:
                await message.answer(response)
                logger.info(
                    f"Sent movie info without poster for: {movie.title}")

        await searching_msg.delete()
        logger.info(
            f"Successfully completed search for user {message.from_user.id}")

    except Exception as e:
        logger.error(
            f"Error processing search request: {str(e)}", exc_info=True)
        await searching_msg.edit_text("😔 Произошла ошибка при поиске фильма. Попробуйте позже.")


async def main():
    await init_db()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
