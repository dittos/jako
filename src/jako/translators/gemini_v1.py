import google.generativeai as genai

from jako.models.prompt import Prompt
from jako.preprocess_html import split_html_chunks


def run_translate(prompt: Prompt):
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=prompt.system,
        generation_config={"temperature": 0.2},
    )
    input_tokens = model.count_tokens(prompt.user).total_tokens
    chars_per_token = len(prompt.user) / input_tokens
    chunk_size = 10000
    print(f"{len(prompt.user)=} {input_tokens=} {chars_per_token=} {chunk_size=}")

    chat = model.start_chat()

    result = ""
    for chunk in split_html_chunks(prompt.user, chunk_size):
        resp = chat.send_message(chunk)
        result += resp.text
        print(resp.usage_metadata)
        print(len(result))

    result = result.replace("```html", "").replace("```", "")
    
    return result
