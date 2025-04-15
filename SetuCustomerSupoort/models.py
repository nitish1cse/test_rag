from pydantic import BaseModel
from typing import List, Optional, Union

class QuestionInput(BaseModel):
    product: str
    question: str


class FeedbackInput(BaseModel):
    question: str
    answer: str
    thumbs_up: bool

class OpenAIConfig(BaseModel):
    api_key: str

class ConfluenceCredentials(BaseModel):
    url: str
    username: str
    api_token: str

class DocumentConfig(BaseModel):
    product: str
    page_ids: List[str]