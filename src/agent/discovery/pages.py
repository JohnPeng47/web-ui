from pydantic import BaseModel, Field
from typing import Optional, List

from httplib import HTTPMessage

class Page(BaseModel):
    url: str
    http_msgs: List[HTTPMessage]