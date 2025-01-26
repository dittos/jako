import json
import os
from pathlib import Path
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from jako.models.page import PageData
from jako.preprocess_html import fix_cite_ref_a, preprocess_split_html, restore_html

app = FastAPI()

web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")


templates = Jinja2Templates(directory=web_dir / "templates")


@app.get("/", response_class=HTMLResponse)
def list_view(request: Request):
    pages = []
    result_dir = Path("data/result")
    for f in os.listdir(result_dir):
        stat = os.stat(result_dir / f)
        page = f.replace(".json", "")
        pages.append({"page": page, "complete": True, "modified": stat.st_mtime})
    
    pages.sort(key=lambda x: x["modified"], reverse=True)

    return templates.TemplateResponse(
        request=request, name="list.html", context={"pages": pages}
    )


@app.get("/wiki/{page}", response_class=HTMLResponse)
def result_view(request: Request, page: str):
    result_path = Path("data/result") / f"{page}.json"
    if not result_path.exists():
        return RedirectResponse(url=f"https://ja.wikipedia.org/wiki/{urllib.parse.quote(page)}")

    data = json.loads(result_path.read_text())
    return templates.TemplateResponse(
        request=request, name="result.html", context={
            "page": page,
            "title": data["title"],
            "html": fix_cite_ref_a(data["html"]),
        }
    )


@app.get("/source", response_class=HTMLResponse)
def source_list_view(request: Request):
    pages = []
    for f in os.listdir(Path("data/source")):
        page = f.replace(".json", "")
        pages.append({"page": page})

    return templates.TemplateResponse(
        request=request, name="source_list.html", context={"pages": pages}
    )


@app.get("/source/{page}", response_class=HTMLResponse)
def source_view(request: Request, page: str, debug: bool = False):
    source_path = Path("data/source") / f"{page}.json"
    
    data = PageData.model_validate_json(source_path.read_text())
    chunks, restore_info = preprocess_split_html(data.page.text, title=data.page.title, size=4096, keep_cite_ref_a=True)
    def _try_restore(chunk: str) -> str:
        try:
            return restore_html(chunk, restore_info)[0]
        except Exception as e:
            return f"<pre>{e}</pre>"
    return templates.TemplateResponse(
        request=request, name="source.html", context={
            "data": data,
            "chunks": [{"raw": chunk, "restored": _try_restore(chunk)} for chunk in chunks],
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("jako.web.server:app", host="0.0.0.0", port=8000, reload=True)
