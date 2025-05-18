import aiohttp
import os
from typing import List, Dict, Optional
from dataclasses import dataclass


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
                for movie in data.get('films', [])[:1]:
                    movie_info = await self._get_movie_details(movie['filmId'])
                    if movie_info:
                        movies.append(movie_info)

                return movies

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
                    title=data.get('nameRu', '') or data.get('nameEn', ''),
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
