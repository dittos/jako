from pathlib import Path

from pydantic import BaseModel, Field

from jako.models.prompt import Prompt


class Generation(BaseModel):
    text: str
    generated_tokens: int
    finish_reason: str


class CheckpointData(BaseModel):
    prompt: Prompt | None = None
    generations: list[Generation] = Field(default_factory=list)
    results_complete: bool = False
    stacktrace: str | None = None


class Checkpoint:
    def __init__(self, path: Path):
        self.path = path
        if self.path.exists():
            self.data = CheckpointData.model_validate_json(path.read_text())
        else:
            self.data = CheckpointData()
    
    def write(self):
        self.path.write_text(self.data.model_dump_json())
