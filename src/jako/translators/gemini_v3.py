import time
import google.generativeai as genai
import google.protobuf.text_format
import google.api_core.exceptions

from jako.checkpoint import Checkpoint, Generation
from jako.models.prompt import Prompt
from jako.preprocess_html import strip_broken_tag, validate_html
from jako.translators.utils import detect_repeated_text


def run_translate(prompt: Prompt, checkpoint: Checkpoint):
    model_max_output_tokens = 8192
    detect_repeated_length = 300

    model_weak = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=prompt.system,
    )
    model_strong = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=prompt.system,
    )
    model = model_weak

    input_tokens = model.count_tokens(prompt.user).total_tokens
    chars_per_token = len(prompt.user) / input_tokens
    print(f"{len(prompt.user)=} {input_tokens=} {chars_per_token=}")

    if checkpoint.data.generations:
        checkpoint.data.generations[-1].text = strip_broken_tag(checkpoint.data.generations[-1].text)
        checkpoint.write()

    results = [g.text for g in checkpoint.data.generations]
    max_output_tokens = model_max_output_tokens

    if not checkpoint.data.results_complete:
        for i in range(1 + input_tokens // model_max_output_tokens * 2):  # TODO: increase if retried
            contents = [
                {"role": "user", "parts": [prompt.user]},
            ]
            if results:
                contents.append({"role": "model", "parts": ["".join(results)]})
            resp = model.generate_content(contents, generation_config={
                "temperature": 0.2,
                "max_output_tokens": max_output_tokens,
            })
            if not resp.candidates:
                raise Exception(f"no candidates generated; stop ({resp=})")
            print(
                resp.candidates[0].finish_reason.name,
                google.protobuf.text_format.MessageToString(genai.protos.GenerateContentResponse.UsageMetadata.pb(resp.usage_metadata), as_one_line=True)
            )
            result = strip_broken_tag(resp.text)
            rep = detect_repeated_text(result, detect_repeated_length)
            if rep:
                if model is model_weak:
                    model = model_strong
                    print(f"repeated text found: {result} '{rep[1]}' @ {rep[0]}; retrying with stronger model")
                    continue
                else:
                    raise Exception(f"repeated text found: {result} '{rep[1]}' @ {rep[0]}")
            else:
                model = model_weak  # restore

            is_valid_html = validate_html("".join(results) + result, prompt.restore_info)
            if not is_valid_html:
                if model is model_weak:
                    model = model_strong
                    print("retrying with stronger model")
                    continue
                else:
                    raise Exception(f"invalid html")
            else:
                model = model_weak  # restore
            
            results.append(result)
            checkpoint.data.generations.append(Generation(
                text=result,
                generated_tokens=resp.usage_metadata.candidates_token_count,
                finish_reason=resp.candidates[0].finish_reason.name,
            ))
            checkpoint.write()
            
            if resp.candidates[0].finish_reason == genai.protos.Candidate.FinishReason.STOP:
                break
        
        checkpoint.data.results_complete = True
        checkpoint.write()

    result = "".join(results)
    result = result.replace("```html", "").replace("```", "")
    
    return result


def generate_content_with_retry(model, **kwargs):
    n = 3
    for i in range(n):
        try:
            return model.generate_content(**kwargs)
        except google.api_core.exceptions.InternalServerError as e:
            if i + 1 == n:
                raise e
            else:
                print(e)
                time.sleep(5)
