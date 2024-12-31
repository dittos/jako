import argparse
import asyncio
from itertools import batched
import json
from pathlib import Path

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

    cache_path = Path("data/cache") / input_path.name
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = Cache(cache_path)
    
    data = PageData.model_validate_json(input_path.read_text())

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
        "Keep all HTML tags, especially keep id attributes."\
        "Try to transliterate names in Japanese language to Hangul."\
        "Don't ask to continue translation.Don't explain about translation."\
        "Don't stop translation early."
    
    responses: list[GoogleGenaiClient.GenerateContentResponse] = []
    for i, batch in enumerate(batched(chunks, 10)):
        print(f"batch {i}...")
        tasks = [
            client.agenerate_content(
                model="gemini-1.5-flash",
                # model="gemini-2.0-flash-exp",
                contents=chunk + "\n\n위 내용을 한국어로 번역하고 자연스러운 한국어로 수정하라.\n\n" + glossary(chunk, data),
                config=dict(
                    system_instruction=system_prompt,
                    max_output_tokens=4096,
                    temperature=0.2,
                ),
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
            raise Exception(f"Unexpected finish reason: {r.candidates[0].finish_reason} for chunk {i}")

    result_htmls = list(recover_start_end_tags(original, r.text) for original, r in zip(chunks, responses))
    result_html = ''.join(result_htmls)
    try:
        result_html, result_title = restore_html(result_html, restore_info)
    except TagMismatchError as e:
        _print_tag_mismatch_error(e, chunks, result_htmls)
        raise e

    result_path.write_text(json.dumps({
        "title": result_title,
        "html": result_html,
    }))

    # cache.flush()


def _print_tag_mismatch_error(e: TagMismatchError, chunks, result_htmls):
    sourceline, sourcepos = e.node.sourceline, e.node.sourcepos
    pos = sum(len(chunk) for chunk in chunks[:sourceline - 1]) + sourcepos
    lastpos = 0
    for i, result_chunk in enumerate(result_htmls):
        if lastpos + len(result_chunk) >= pos:
            pos_in_chunk = pos - lastpos
            original_pos_in_chunk = chunks[i].find(f"<{e.expected_tag} id=\"{e.node_id}\"")
            print(str(e))
            print(f"Original:   {repr(chunks[i][max(original_pos_in_chunk-20, 0):min(original_pos_in_chunk+100, len(chunks[i]))])}")
            print(f"Translated: {repr(result_chunk[max(pos_in_chunk-20, 0):min(pos_in_chunk+100, len(result_chunk))])}")
            break
        lastpos += len(result_chunk)


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
        await process(input_path, overwrite=args.overwrite)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input file")
    parser.add_argument("--overwrite", action="store_true")
    asyncio.run(main(parser.parse_args()))
