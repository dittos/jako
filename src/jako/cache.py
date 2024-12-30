import asyncio
import json
from pathlib import Path
from typing import Callable, TypedDict


class CacheEntry(TypedDict):
    args: list
    kwargs: dict
    result: object


class Cache:
    _path: Path
    _data: dict[str, list[CacheEntry]]

    def __init__(self, path: Path):
        self._path = path
        self._data = json.loads(path.read_text()) if path.exists() else {}

    def wrap(self, scope: str, func: Callable, encode_result: Callable, decode_result: Callable):
        if asyncio.iscoroutinefunction(func):
            async def wrapper(*args, **kwargs):
                cached, found = self.lookup(scope, args, kwargs, decode_result)
                if found:
                    return cached
                result = await func(*args, **kwargs)
                self.set(scope, args, kwargs, result, encode_result)
                self.flush()
                return result
        else:
            def wrapper(*args, **kwargs):
                cached, found = self.lookup(scope, args, kwargs, decode_result)
                if found:
                    return cached
                result = func(*args, **kwargs)
                self.set(scope, args, kwargs, result, encode_result)
                self.flush()
                return result
        return wrapper

    def lookup(self, scope: str, args: tuple, kwargs: dict, decode_result: Callable):
        for entry in self._data.get(scope, []):
            if entry["args"] == list(args) and entry["kwargs"] == kwargs:
                return decode_result(entry["result"]), True
        return None, False
    
    def set(self, scope: str, args: tuple, kwargs: dict, result: object, encode_result: Callable):
        if scope not in self._data:
            self._data[scope] = []
        self._data[scope].append({
            "args": args,
            "kwargs": kwargs,
            "result": encode_result(result),
        })
    
    def flush(self):
        self._path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))
