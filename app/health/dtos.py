from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1000)
    document_types: list[str] | None = Field(default=None, max_length=10)
    date_from: date | None = None
    date_to: date | None = None
    document_ids: list[UUID] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_filters(self):
        self.question = self.question.strip()
        if not self.question:
            raise ValueError("question must not be blank")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        if self.document_types is not None:
            self.document_types = list(dict.fromkeys(item.strip().lower() for item in self.document_types if item.strip()))
        if self.document_ids is not None:
            self.document_ids = list(dict.fromkeys(self.document_ids))
        return self


class Citation(BaseModel):
    document_id: UUID
    document_name: str
    page_number: int | None


class EvidenceItem(Citation):
    excerpt: str


class HealthAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    evidence: list[EvidenceItem]
    generation_status: str = "generated"


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question: str
    answer: str
    generation_status: str = "generated"
    citations: list[Citation]
    created_at: datetime
