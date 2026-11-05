"""Course Advisor AI — API input contract (Pydantic v2)."""
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Level(str, Enum):
    beginner = 'beginner'
    intermediate = 'intermediate'
    advanced = 'advanced'


class LearningRequest(StrictModel):
    topic: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    level: Level | None = None

    @field_validator('description', mode='after')
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value or None


class Preferences(StrictModel):
    language: str | None = Field(default=None, min_length=2, max_length=30)
    format: Literal['in_person', 'live_online', 'recorded_online', 'hybrid'] | None = None
    learning_style: Literal['practical', 'theoretical', 'mixed'] | None = None
    certificate: Literal['required', 'preferred', 'not_important'] | None = None


class Budget(StrictModel):
    mode: Literal['free', 'limited', 'unrestricted'] | None = None
    max_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @model_validator(mode='after')
    def check_budget(self):
        if self.mode == 'limited' and (self.max_amount is None or not self.currency):
            raise ValueError('Limited budget requires max_amount and 3-letter currency.')
        if self.mode != 'limited' and (self.max_amount is not None or self.currency is not None):
            raise ValueError('max_amount/currency are supported only with mode=limited.')
        return self


class Constraints(StrictModel):
    budget: Budget = Field(default_factory=Budget)
    location: str | None = Field(default=None, max_length=150)
    weekly_hours: float | None = Field(default=None, gt=0, le=168)
    duration: Literal['short', 'medium', 'long'] | None = None


class Settings(StrictModel):
    hard_constraints: list[Literal['language', 'format', 'learning_style', 'certificate', 'budget', 'location', 'weekly_hours', 'duration']] = Field(default_factory=list)


class CourseAdvisorInput(StrictModel):
    learning_request: LearningRequest
    preferences: Preferences = Field(default_factory=Preferences)
    constraints: Constraints = Field(default_factory=Constraints)
    settings: Settings = Field(default_factory=Settings)

    @model_validator(mode='after')
    def check_hard_constraints(self):
        values = {
            'language': self.preferences.language,
            'format': self.preferences.format,
            'learning_style': self.preferences.learning_style,
            'certificate': self.preferences.certificate,
            'budget': self.constraints.budget.mode,
            'location': self.constraints.location,
            'weekly_hours': self.constraints.weekly_hours,
            'duration': self.constraints.duration,
        }
        if len(self.settings.hard_constraints) != len(set(self.settings.hard_constraints)):
            raise ValueError('hard_constraints contains duplicates.')
        missing = [name for name in self.settings.hard_constraints if values[name] is None]
        if missing:
            raise ValueError(f'Hard constraints require values: {missing}')
        return self
