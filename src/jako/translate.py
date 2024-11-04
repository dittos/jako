from datetime import datetime

from jako.models.page import PageData
from jako.preprocess_html import restore_html
from jako.prompts.translate_v1 import translate


if __name__ == "__main__":
    import sys
    from pathlib import Path
    data = PageData.model_validate_json(Path(sys.argv[1]).read_text())
    prompt = translate(data, keep_cite_ref_a=True)
    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"writing to tmp/result-{version}.html")
    Path(f"tmp/result-{version}-input.html").write_text(prompt.user)

    # import google.generativeai as genai
    # import os
    # genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    # from jako.translators.gemini_v3 import run_translate
    
    from jako.translators.openai_v1 import run_translate

    raw = run_translate(prompt)
    Path(f"tmp/result-{version}-raw.html").write_text(raw)

    html, title = restore_html(raw, prompt.restore_info)
    Path(f"tmp/result-{version}.html").write_text(html)
    print(title)
