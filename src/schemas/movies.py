from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from database.models import MovieStatusEnum


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: str


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int

    class Config:
        from_attributes = True


class MovieBase(BaseModel):
    name: str
    date: date
    score: float
    overview: str
    status: MovieStatusEnum
    budget: float
    revenue: float
    country: str
    genres: List[str]
    actors: List[str]
    languages: List[str]


class MovieCreate(MovieBase):
    pass


class NameIdBase(BaseModel):
    id: int
    name: Optional[str] = None


class Country(NameIdBase):
    code: Optional[str] = None


class MovieDetailSchema(BaseModel):
    name: str
    date: date
    score: float
    overview: str
    status: MovieStatusEnum
    budget: float
    revenue: float
    country: Country
    genres: List[NameIdBase]
    actors: List[NameIdBase]
    languages: List[NameIdBase]

    class Config:
        from_attributes = True


class MovieUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    score: Optional[float] = None
    overview: Optional[str] = None
    status: Optional[MovieStatusEnum] = None
    budget: Optional[float] = None
    revenue: Optional[float] = None
