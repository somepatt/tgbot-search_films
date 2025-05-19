import aiohttp
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
from random import randint, choice, sample, random, shuffle
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MovieInfo:
    title: str
    overview: str
    rating: float
    poster_url: str
    release_date: str
    movie_id: str
    viewing_links: List[str]
    genres: List[str]
    countries: List[str]
    film_length: str


class MovieSearcher:
    def __init__(self):
        self.api_key = os.getenv('KINOPOISK_API_KEY')
        self.search_url = f"https://kinopoiskapiunofficial.tech/api/v2.1/films/search-by-keyword"
        self.movie_url = f"https://kinopoiskapiunofficial.tech/api/v2.2/films"
        self.top250_url = f"https://kinopoiskapiunofficial.tech/api/v2.2/films/top"
        self._top250_cache = None
        self._cache_timestamp = None
        self._cache_duration = 3600

    async def _fetch_top250_from_api(self) -> List[Dict]:
        """Получает список топ-250 фильмов напрямую из API"""
        async with aiohttp.ClientSession() as session:
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }

            all_movies = []
            try:
                # Кинопоиск API возвращает по 20 фильмов на страницу
                for page in range(1, 13):  # 13 страниц * 20 фильмов = 250 фильмов
                    params = {
                        'type': 'TOP_250_BEST_FILMS',
                        'page': page
                    }

                    async with session.get(self.top250_url, headers=headers, params=params) as response:
                        if response.status != 200:
                            logger.error(
                                f"Error getting top movies page {page}: {response.status}")
                            continue

                        data = await response.json()
                        if not data or 'films' not in data:
                            logger.error(
                                f"Invalid response format for page {page}")
                            continue

                        movies = data.get('films', [])
                        if not movies:
                            logger.error(f"No movies found on page {page}")
                            continue

                        all_movies.extend(movies)
                        logger.info(
                            f"Got {len(movies)} movies from page {page}")

                logger.info(
                    f"Total movies collected from API: {len(all_movies)}")
                return all_movies

            except Exception as e:
                logger.error(
                    f"Error getting top 250 movies from API: {str(e)}", exc_info=True)
                return []

    async def _update_top250_cache(self) -> None:
        """Обновляет кэш топ-250 фильмов"""
        logger.info("Updating top 250 movies cache...")
        self._top250_cache = await self._fetch_top250_from_api()
        self._cache_timestamp = datetime.now().timestamp()
        logger.info(
            f"Cache updated with {len(self._top250_cache) if self._top250_cache else 0} movies")

    async def get_top250_movies(self) -> List[Dict]:
        """Получает список топ-250 фильмов, используя кэш если он актуален"""
        current_time = datetime.now().timestamp()

        # Если кэш пустой или устарел, обновляем его
        if (self._top250_cache is None or
            self._cache_timestamp is None or
                current_time - self._cache_timestamp > self._cache_duration):
            await self._update_top250_cache()

        return self._top250_cache or []

    async def search_movie(self, query: str) -> List[MovieInfo]:
        async with aiohttp.ClientSession() as session:
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }

            params = {
                'keyword': query
            }

            async with session.get(self.search_url, headers=headers, params=params) as response:
                if response.status != 200:
                    return []

                data = await response.json()
                movies = []
                for movie in data.get('films', [])[:5]:
                    movie_info = await self._get_movie_details(movie['filmId'])
                    if movie_info:
                        movies.append(movie_info)

                return movies

    async def random_movie(self) -> List[MovieInfo]:
        try:
            # Получаем список топ-250 фильмов
            top_movies = await self.get_top250_movies()
            if not top_movies:
                return []
            shuffle(top_movies)

            # Выбираем случайный фильм из списка
            random_movie = top_movies[0]
            movie_id = random_movie['filmId']

            # Получаем детальную информацию о фильме
            async with aiohttp.ClientSession() as session:
                headers = {
                    'X-API-KEY': self.api_key,
                    'Content-Type': 'application/json'
                }

                async with session.get(f"{self.movie_url}/{movie_id}", headers=headers) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    genres = [genre['genre']
                              for genre in data.get('genres', [])]
                    countries = [country['country']
                                 for country in data.get('countries', [])]

                    viewing_links = [
                        f"https://www.kinopoisk.vip/film/{movie_id}/"
                    ]

                    rating_str = data.get('ratingKinopoisk', '0')
                    try:
                        rating = float(rating_str)
                    except:
                        rating = 0.0

                    return [MovieInfo(
                        title=data.get('nameRu', '') or data.get(
                            'nameEn', '') or data.get('nameOriginal', ''),
                        overview=data.get('description', '')[
                            :150] + '...' if data.get('description', '') else '',
                        rating=rating,
                        poster_url=data.get('posterUrl', ''),
                        release_date=data.get('year', ''),
                        movie_id=str(movie_id),
                        viewing_links=viewing_links,
                        genres=genres,
                        countries=countries,
                        film_length=data.get('filmLength', '')
                    )]
        except Exception as e:
            logger.error(
                f"Error getting random movie: {str(e)}", exc_info=True)
            return []

    async def _get_movie_details(self, movie_id: int) -> Optional[MovieInfo]:
        async with aiohttp.ClientSession() as session:
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }

            async with session.get(f"{self.movie_url}/{movie_id}", headers=headers) as response:
                if response.status != 200:
                    return None

                data = await response.json()

                genres = [genre['genre'] for genre in data.get('genres', [])]
                countries = [country['country']
                             for country in data.get('countries', [])]

                viewing_links = [
                    f"https://www.kinopoisk.vip/film/{movie_id}/"
                ]

                rating_str = data.get('ratingKinopoisk', '0')
                try:
                    rating = float(rating_str)
                except:
                    rating = 0.0

                return MovieInfo(
                    title=data.get('nameRu', '') or data.get(
                        'nameEn', '') or data.get('nameOriginal', ''),
                    overview=data.get('description', '')[
                        :150] + '...' if data.get('description', '') else '',
                    rating=rating,
                    poster_url=data.get('posterUrl', ''),
                    release_date=data.get('year', ''),
                    movie_id=str(movie_id),
                    viewing_links=viewing_links,
                    genres=genres,
                    countries=countries,
                    film_length=data.get('filmLength', '')
                )

    async def get_random_movies_for_game(self, count: int = 4) -> List[MovieInfo]:
        """Get random movies for the game, ensuring they have descriptions"""
        try:
            logger.info("Getting top 250 movies for game...")
            # Получаем список топ-250 фильмов
            top_movies = await self.get_top250_movies()
            if not top_movies:
                logger.error("No top 250 movies found")
                return []
            shuffle(top_movies)

            logger.info(f"Found {len(top_movies)} top movies")
            # Фильтруем фильмы, у которых есть описание
            movies_with_description = []
            for movie in top_movies:
                movie_info = await self._get_movie_details(movie['filmId'])
                if movie_info and movie_info.overview:
                    movies_with_description.append(movie_info)
                    logger.info(
                        f"Added movie with description: {movie_info.title}")
                # Берем в 2 раза больше для разнообразия
                if len(movies_with_description) >= count * 3:
                    break

            logger.info(
                f"Found {len(movies_with_description)} movies with descriptions")
            # Выбираем случайные фильмы
            if len(movies_with_description) < count:
                logger.error(
                    f"Not enough movies with descriptions. Found: {len(movies_with_description)}, needed: {count}")
                return []

            selected_movies = sample(movies_with_description, count)
            logger.info(
                f"Selected {len(selected_movies)} random movies for game")
            return selected_movies
        except Exception as e:
            logger.error(
                f"Error getting random movies for game: {str(e)}", exc_info=True)
            return []

    def get_movie_description_for_game(self, movie: MovieInfo) -> str:
        """Get a game-appropriate description of the movie"""
        description = movie.overview
        # Убираем название фильма из описания, если оно там есть
        description = description.replace(movie.title, "***")
        return description
