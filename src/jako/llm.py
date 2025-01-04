import asyncio
import os
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from jako.cache import Cache


class GoogleGenaiClient:
    GenerateContentResponse = types.GenerateContentResponse

    def __init__(self):
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    async def agenerate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnionDict,
        config: types.GenerateContentConfigOrDict | None = None,
        cache: Cache,
    ) -> types.GenerateContentResponse:  
        def encode_result(result):
            return types.GenerateContentResponse.model_dump(result, mode="json")
        
        def decode_result(result):
            if not result.get("parsed"):
                result["parsed"] = {}  # workaround
            return types.GenerateContentResponse(**result)
        
        return await cache.wrap("google", self._agenerate_content_with_retry, encode_result, decode_result)(
            model=model,
            contents=contents,
            config=config,
        )
    
    async def _agenerate_content_with_retry(
        self,
        *,
        model: str,
        contents: types.ContentListUnionDict,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse:
        for _ in range(10):
            try:
                return await self._client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
            except ClientError as e:
                if e.code == 429:
                    await asyncio.sleep(10)
                    continue
                raise
        raise Exception("retry failed")
