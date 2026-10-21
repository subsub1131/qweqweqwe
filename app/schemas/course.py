"""Validated request and response shapes for the memory-only course demo."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]

class CourseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[Text, Field(max_length=200)]
    description: Annotated[Text, Field(max_length=10000)]
    category: Annotated[Text, Field(max_length=100)]
    price: Annotated[int, Field(strict=True, ge=0)]
    duration_minutes: PositiveInt
    lesson_count: PositiveInt

class Course(CourseInput):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: PositiveInt
    instructor: str

class CourseList(BaseModel):
    items: list[Course]

class PurchaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: PositiveInt

class DemoPurchase(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    course: Course
    demo: Literal[True] = True
