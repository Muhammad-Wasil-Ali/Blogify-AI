from datetime import datetime

from pydantic import BaseModel


class GenerateBlogRequest(BaseModel):
    topic: str


class BlogResponse(BaseModel):
    id: str
    topic: str
    title: str
    intro_summary: str
    content: str
    created_at: datetime
