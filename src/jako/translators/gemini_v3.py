import google.generativeai as genai

from jako.models.prompt import Prompt


def run_translate(prompt: Prompt):
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=prompt.system,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 8192,
        },
    )
    input_tokens = model.count_tokens(prompt.user).total_tokens
    chars_per_token = len(prompt.user) / input_tokens
    print(f"{len(prompt.user)=} {input_tokens=} {chars_per_token=}")

    result = ""

    for i in range(input_tokens // 8192 + 3):
        contents = [
            {"role": "user", "parts": [prompt.user]},
        ]
        if result:
            contents.append({"role": "model", "parts": [result]})
        resp = model.generate_content(contents)
        if not resp.candidates:
            break
        result += resp.text
        print(resp.usage_metadata)
        print(len(result))
        if resp.candidates[0].finish_reason == genai.protos.Candidate.FinishReason.STOP:
            break

    result = result.replace("```html", "").replace("```", "")
    
    return result
