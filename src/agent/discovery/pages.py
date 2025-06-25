from pydantic import BaseModel, Field
from typing import Optional, List

from httplib import HTTPMessage

class Subpage(BaseModel):
    url: str
    name: str
    description: str
    contents: str
    plan_steps: Optional[List[str]] # the plans executed by the agent to get here from the main page

class Page(BaseModel):
    url: str
    mainpage_contents: str
    subpages: List[Subpage] = Field(default_factory=list)
    http_msgs: List[HTTPMessage]
    description: Optional[str]
    title: Optional[str]

    # TODO: implement this method to return mainpage_contents + diff of all contents from the subpages
    # with the subpage contents labeled
    @property
    def page_contents(self) -> str:
        pass

# NOTES:
# - holds a to_visit list of urls
# - pop() pops a url, creates a Page object, and assigns to current_page
# - this initialization should work for server side too as well, where pop requests 
# a url from the server
class Pages:
    def __init__(self, items=None):
        self._dict = {}
        if items:
            for item in items:
                self.add(item)
    
    def add(self, item):
        self._dict[item] = None
    
    def pop(self, index=-1):
        if not self._dict:
            raise IndexError("pop from empty Pages")
        
        keys = list(self._dict.keys())
        
        try:
            item = keys[index]
            del self._dict[item]
            return item
        except IndexError:
            raise IndexError("pop index out of range")