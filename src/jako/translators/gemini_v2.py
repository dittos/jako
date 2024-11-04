import google.generativeai as genai

from jako.models.prompt import Prompt


def run_translate(prompt: Prompt):
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=prompt.system,
        generation_config={
            "temperature": 0.2,
            "stop_sequences": ["!!STOP!!"],
            "max_output_tokens": 8192,
        },
    )
    input_tokens = model.count_tokens(prompt.user).total_tokens
    chars_per_token = len(prompt.user) / input_tokens
    print(f"{len(prompt.user)=} {input_tokens=} {chars_per_token=}")

    result = ""
    chat = model.start_chat()

    for i in range(100):
        if i == 0:
            message = prompt.user
        else:
            message = "Continue the translation. Say `!!STOP!!` if done."

        resp = chat.send_message(message)
        # TODO: remove broken html from assistant message (can i modify ChatSession history?)
        result += resp.text
        print(resp.usage_metadata)
        print(len(result))
        if resp.candidates[0].finish_reason == genai.protos.Candidate.FinishReason.STOP:
            break

    result = result.replace("```html", "").replace("```", "")
    
    return result
