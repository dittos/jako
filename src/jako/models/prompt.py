from typing import Any
from pydantic import BaseModel


class CiteRefRestoreInfo(BaseModel):
    a_attrs: dict[str, str | Any] | None
    pre: str
    post: str


class RestoreInfo(BaseModel):
    metadata_tags: list[str]
    attrs: dict[int, dict[str, str | Any]]
    cite_refs: dict[str, CiteRefRestoreInfo]
    references: dict[str, str] = {}


class Prompt(BaseModel):
    system: str
    user: str
    restore_info: RestoreInfo
