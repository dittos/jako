from datetime import datetime
import json
from pathlib import Path
import traceback

from jako.checkpoint import Checkpoint
from jako.models.page import PageData
from jako.preprocess_html import restore_html
from jako.prompts.translate_v1 import translate

import google.generativeai as genai
import os
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
from jako.translators.gemini_v3 import run_translate

# from jako.translators.openai_v1 import run_translate


def translate_file(source_path: Path) -> bool:
    result_path = Path("data/result") / source_path.name
    if result_path.exists():
        print(f"skip translation: {source_path}")
        return False

    print(f"translating: {source_path}")
    checkpoint_path = Path("data/checkpoint") / source_path.name
    checkpoint = Checkpoint(checkpoint_path)

    prompt = checkpoint.data.prompt
    if prompt is None:
        data = PageData.model_validate_json(source_path.read_text())
        prompt = translate(data, keep_cite_ref_a=True)
        checkpoint.data.prompt = prompt
        checkpoint.write()
    
    try:
        raw = run_translate(prompt, checkpoint)
        html, title = restore_html(raw, prompt.restore_info)
        result_path.write_text(json.dumps({
            "title": title,
            "html": html,
        }, indent=2, ensure_ascii=False))
    except Exception:
        checkpoint.data.stacktrace = traceback.format_exc()
        checkpoint.write()
        print(checkpoint.data.stacktrace)
    
    return True


if __name__ == "__main__":
    import sys
    # translate_file(Path(sys.argv[1]))
    with open(sys.argv[1]) as f:
        base_dir = Path("data/source")
        for line in f:
            filename = line.strip()
            try:
                if translate_file(base_dir / filename):
                    break
            except Exception:
                traceback.print_exc()
