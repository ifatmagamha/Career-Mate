# src/storage/io.py
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def save_json(path: str | Path, items: List[BaseModel]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([x.model_dump(mode="json") for x in items], f, ensure_ascii=False, indent=2)


def load_json(path: str | Path, schema: Type[T]) -> List[T]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [schema.model_validate(x) for x in data]
