import openai
import tiktoken

from jako.models.prompt import Prompt


def run_translate(prompt: Prompt, model: str = "gpt-4o-mini"):
    enc = tiktoken.encoding_for_model(model)
    print(f"input tokens: {len(enc.encode(prompt.system + prompt.user))}")

    resp = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        temperature=0.2,
    )

    # TODO: handle max output tokens over
    result = resp.choices[0].message.content
    result = result.replace("```html", "").replace("```", "")
    
    return result
