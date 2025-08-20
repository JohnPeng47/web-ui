from pydantic import BaseModel, Field
from typing import Optional, List

from httplib import HTTPMessage

class Page(BaseModel):
    url: str
    http_msgs: List[HTTPMessage] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)

    def add_http_msg(self, msg: HTTPMessage):
        self.http_msgs.append(msg)

    def add_link(self, link: str):
        if link not in self.links:
            self.links.append(link)

    def __str__(self):
        links_str = "\n".join([f"  - {link}" for link in self.links])
        http_msgs_str = "\n".join([f"  - [{msg.method}] {msg.url}\n{msg.body if msg.body else ''}" for msg in self.http_msgs])
        
        result = f"Page: {self.url}\n"
        if self.links:
            result += f"Links ({len(self.links)}):\n{links_str}\n"
        if self.http_msgs:
            result += f"HTTP Messages ({len(self.http_msgs)}):\n{http_msgs_str}\n"
        
        return result.rstrip()