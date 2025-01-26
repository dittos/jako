import argparse
import asyncio
from itertools import batched
import json
from pathlib import Path
import traceback

from jako.cache import Cache
from jako.llm import GoogleGenaiClient
from jako.models.page import PageData
from jako.preprocess_html import TagMismatchError, preprocess_split_html, recover_start_end_tags, restore_html
from jako.prompts.glossary import glossary


async def process(input_path: Path, overwrite: bool = False):
    result_path = Path("data/result") / input_path.name
    if result_path.exists() and not overwrite:
        print(f"Result file {result_path} already exists. Use --overwrite to overwrite.")
        return
    
    data = PageData.model_validate_json(input_path.read_text())

    cache_path = Path("data/cache") / f"{data.page.pageid}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    print("Using cache:", cache_path)
    cache = Cache(cache_path)

    chunks, restore_info = preprocess_split_html(
        data.page.text,
        data.page.title,
        4096,
        keep_cite_ref_a=True,
    )
    print(f"{len(chunks)=}")

    client = GoogleGenaiClient()

    system_prompt = "You are a professional Japanese to Korean translator."\
        "Don't use Kanji,Hiragana,Katakana.Only use Hangul."\
        "Keep all HTML tags, especially keep id attributes.Do NOT add new HTML tags."\
        "Try to transliterate names in Japanese language to Hangul."\
        "Don't ask to continue translation.Don't explain about translation."\
        "Don't stop translation early."

    max_output_tokens = 8192    
    chunk_args = []
    for i, chunk in enumerate(chunks):
        prompt = chunk + "\n\n위 내용을 한국어로 번역하고 자연스러운 한국어로 수정하라.\n\n" + glossary(chunk, data)
        if len(prompt) > max_output_tokens:
            raise ValueError(f"chunk {i} is too large: {len(prompt)}")
        chunk_args.append({
            "model": "gemini-1.5-flash",
            # "model": "gemini-2.0-flash-exp",
            "contents": prompt,
            "config": {
                "system_instruction": system_prompt,
                "max_output_tokens": min(len(prompt), max_output_tokens),
                "temperature": 0.2,
            },
            "retry_count": 0,
        })
    
    while True:
        responses: list[GoogleGenaiClient.GenerateContentResponse] = []
        for i, batch in enumerate(batched(chunk_args, 4)):
            print(f"batch {i}...")
            tasks = [
                client.agenerate_content(
                    model=chunk["model"],
                    contents=chunk["contents"],
                    config=chunk["config"],
                    cache=cache,
                )
                for chunk in batch
            ]
            batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_responses:
                if isinstance(r, Exception):
                    raise r
                else:
                    responses.append(r)

        for i, r in enumerate(responses):
            if r.candidates[0].finish_reason != "STOP":
                raise Exception(f"Unexpected finish reason: {r.candidates[0].finish_reason} for chunk #{i}")

        result_chunks = list(recover_start_end_tags(original, r.text) for original, r in zip(chunks, responses))
        result_html = ''.join(result_chunks)
        try:
            result_html, result_title = restore_html(result_html, restore_info)
        except TagMismatchError as e:
            match = _find_tag_mismatch_chunk_index(e, result_html, result_chunks)
            if not match:
                print("Tag mismatch chunk not found")
                raise e
            
            error_chunk_index, _ = match
            if chunk_args[error_chunk_index]["retry_count"] > 0:
                _print_tag_mismatch_error(e, chunks, result_chunks, result_html)
                raise e
            print(f"Retrying error chunk {error_chunk_index}")
            chunk_args[error_chunk_index]["retry_count"] += 1
            chunk_args[error_chunk_index]["model"] = "gemini-2.0-flash-exp"
            # chunk_args[error_chunk_index]["model"] = "gemini-1.5-flash"
        else:
            break

    result_path.write_text(json.dumps({
        "title": result_title,
        "html": result_html,
    }))

    # cache.flush()


def _find_tag_mismatch_chunk_index(e: TagMismatchError, result_html, result_chunks):
    sourceline, sourcepos = e.node.sourceline, e.node.sourcepos
    pos = sum(len(line) for line in result_html.splitlines(keepends=True)[:sourceline - 1]) + sourcepos
    result_chunk_start = 0
    for i, result_chunk in enumerate(result_chunks):
        next_result_chunk_start = result_chunk_start + len(result_chunk)
        if pos < next_result_chunk_start:
            return i, pos - result_chunk_start
        result_chunk_start = next_result_chunk_start
    return None


def _print_tag_mismatch_error(e: TagMismatchError, chunks, result_chunks, result_html):
    match = _find_tag_mismatch_chunk_index(e, result_html, result_chunks)
    if not match:
        print("Tag mismatch chunk not found")
        return
    
    error_chunk_index, pos_in_result_chunk = match
    result_chunk = result_chunks[error_chunk_index]
    original_chunk = chunks[error_chunk_index]
    pos_in_original_chunk = original_chunk.find(f"<{e.expected_tag} id=\"{e.node_id}\"")
    print(str(e))
    if pos_in_original_chunk == -1:
        print("Original tag not found")
    else:
        print(f"Original:   {repr(original_chunk[max(pos_in_original_chunk-20, 0):min(pos_in_original_chunk+200, len(original_chunk))])}")
    print(f"Translated: {repr(result_chunk[max(pos_in_result_chunk-20, 0):min(pos_in_result_chunk+200, len(result_chunk))])}")


async def main(args):
    input_path = Path(args.input)

    input_paths = []
    if input_path.suffix == ".csv":
        with open(input_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                input_paths.append(Path("data/source") / f"{line.replace('/', '__')}.json")
    else:
        input_paths = [input_path]
    
    for input_path in input_paths:
        print(f"Processing {input_path}")
        try:
            await process(input_path, overwrite=args.overwrite)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input file")
    parser.add_argument("--overwrite", action="store_true")
    asyncio.run(main(parser.parse_args()))
