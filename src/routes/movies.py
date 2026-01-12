import math
import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas.movies import MovieListResponseSchema, MovieDetailSchema, MovieCreate, MovieUpdate

router = APIRouter()

# Write your code here


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movies(
        request: Request,
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20),
        db: AsyncSession = Depends(get_db)
):
    total_items = await db.scalar(select(func.count()).select_from(MovieModel))
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")
    total_pages = math.ceil(total_items / per_page)
    if page > 1:
        prev_page = f"/theater/movies/?page={page - 1}&per_page={per_page}"
        start = (page - 1) * per_page
    elif page == 1:
        prev_page = None
        start = 0
    else:
        raise HTTPException(status_code=404, detail="Page does not exist.")

    if page == total_pages:
        next_page = None
    elif page < total_pages:
        next_page = f"/theater/movies/?page={page + 1}&per_page={per_page}"
    else:
        raise HTTPException(status_code=404, detail="No movies found.")

    result = await db.execute(
        select(MovieModel)
        .order_by(desc(MovieModel.id))
        .limit(per_page)
        .offset(start)
    )
    movies = result.scalars().all()
    return {
        "movies": movies,
        "prev_page": prev_page,
        "next_page": next_page,
        "total_pages": total_pages,
        "total_items": total_items,
    }


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_movie(movie: MovieCreate, db: AsyncSession = Depends(get_db)):
    if len(movie.name) > 255:
        raise HTTPException(status_code=400, detail="Bad Request")
    if movie.date - datetime.date.today() > datetime.timedelta(days=365):
        raise HTTPException(status_code=400, detail="Bad Request")
    unique_check = await db.execute(select(MovieModel).where(
        MovieModel.name == movie.name,
        MovieModel.date == movie.date
    ))
    if unique_check.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name "
                   f"'{movie.name}' and release "
                   f"date '{movie.date}' already exists."
        )
    if movie.score < 0 or movie.score > 100:
        raise HTTPException(status_code=400, detail="Bad Request")
    if movie.budget < 0 or movie.revenue < 0:
        raise HTTPException(status_code=400, detail="Bad Request")
    if movie.country.find("(") != -1:
        country_name, country_code = movie.country.rsplit(" (", 1)
        country_code = country_code.rstrip(")")
        country = await db.execute(select(CountryModel).where(
            CountryModel.code == country_code,
            CountryModel.name == country_name
        ))
        country = country.scalar_one_or_none()
        if country is None:
            country = CountryModel(
                name=country_name,
                code=country_code,
            )
            db.add(country)
            await db.commit()
            await db.refresh(country)
    else:
        country_code = movie.country
        country = await db.execute(
            select(CountryModel)
            .where(CountryModel.code == country_code)
        )
        if country.scalar_one_or_none() is None:
            country = CountryModel(code=country_code)
            db.add(country)
            await db.commit()
            await db.refresh(country)
        country = country.scalar_one_or_none()
    genres = await create_missing_genres(db, movie.genres)
    actors = await create_missing_actors(db, movie.actors)
    languages = await create_missing_languages(db, movie.languages)
    new_movie = MovieModel(
        name=movie.name,
        date=movie.date,
        score=movie.score,
        overview=movie.overview,
        status=movie.status,
        budget=movie.budget,
        revenue=movie.revenue,
        country=country,
        genres=genres,
        actors=actors,
        languages=languages,
    )
    db.add(new_movie)
    await db.commit()
    return new_movie


@router.get("/movies/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MovieModel)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
        .where(MovieModel.id == movie_id)
    )
    movie = result.scalar_one_or_none()
    if movie:
        return movie
    else:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")


@router.delete("/movies/{movie_id}/")
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = result.scalar_one_or_none()
    if movie:
        await db.delete(movie)
        await db.commit()
        return Response(status_code=204)
    raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")


@router.patch("/movies/{movie_id}/")
async def update_movie(movie_id: int, movie: MovieUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    db_movie = result.scalar_one_or_none()
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    if movie.name:
        db_movie.name = movie.name
    if movie.date:
        db_movie.date = movie.date
    if movie.score:
        if 0 <= movie.score <= 100:
            db_movie.score = movie.score
        else:
            raise HTTPException(status_code=400, detail="Invalid input data.")
    if movie.overview:
        db_movie.overview = movie.overview
    if movie.status:
        db_movie.status = movie.status
    if movie.budget:
        if movie.budget >= 0:
            db_movie.budget = movie.budget
        else:
            raise HTTPException(status_code=400, detail="Invalid input data.")
    if movie.revenue:
        if movie.revenue >= 0:
            db_movie.revenue = movie.revenue
        else:
            raise HTTPException(status_code=400, detail="Invalid input data.")
    await db.commit()
    return JSONResponse(
        status_code=200,
        content={"detail": "Movie updated successfully."}
    )


async def create_missing_genres(db: AsyncSession, names: List[str]) -> List[GenreModel]:
    genres = []
    for name in names:
        result = await db.execute(select(GenreModel).where(GenreModel.name == name))
        genre = result.scalar_one_or_none()
        if genre is None:
            genre = GenreModel(name=name)
            db.add(genre)
        genres.append(genre)
    await db.commit()
    await db.refresh(genres)
    return genres


async def create_missing_actors(db: AsyncSession, names: List[str]) -> List[ActorModel]:
    actors = []
    for name in names:
        result = await db.execute(select(ActorModel).where(ActorModel.name == name))
        actor = result.scalar_one_or_none()
        if actor is None:
            actor = ActorModel(name=name)
            db.add(actor)
        actors.append(actor)
    await db.commit()
    await db.refresh(actors)
    return actors


async def create_missing_languages(db: AsyncSession, names: List[str]) -> List[LanguageModel]:
    languages = []
    for name in names:
        result = await db.execute(select(LanguageModel).where(LanguageModel.name == name))
        language = result.scalar_one_or_none()
        if language is None:
            language = LanguageModel(name=name)
            db.add(language)
        languages.append(language)
    await db.commit()
    await db.refresh(languages)
    return languages
