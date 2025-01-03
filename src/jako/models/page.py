from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class Langlink(BaseModel):
    lang: str
    title: str

    model_config = ConfigDict(extra='allow')


class Link(BaseModel):
    ns: int
    title: str
    exists: bool

    model_config = ConfigDict(extra='allow')


class Redirect(BaseModel):
    from_: str = Field(alias='from')
    to: str
    tofragment: str | None = None


class Page(BaseModel):
    title: str
    text: str
    revid: int
    langlinks: list[Langlink]
    links: list[Link]
    redirects: list[Redirect] = []

    model_config = ConfigDict(extra='allow')


class PageLanglinks(BaseModel):
    pageid: int
    ns: int
    title: str
    langlinks: list[Langlink] | None = None


class PageRevision(BaseModel):
    revid: int
    parentid: int
    minor: bool


    model_config = ConfigDict(extra='allow')


class PageData(BaseModel):
    page: Page
    links_langlinks: list[PageLanglinks]
    last_rev_timestamp: datetime
    metadata: dict = {}
