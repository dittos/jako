import json
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from jako.models.page import PageData
from jako.preprocess_html import preprocess_split_html

app = FastAPI()

web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")


templates = Jinja2Templates(directory=web_dir / "templates")


@app.get("/", response_class=HTMLResponse)
def list_view(request: Request):
    pages = []
    for f in os.listdir(Path("data/result")):
        page = f.replace(".json", "")
        pages.append({"page": page, "complete": True})

    return templates.TemplateResponse(
        request=request, name="list.html", context={"pages": pages}
    )


@app.get("/result/{page}", response_class=HTMLResponse)
def result_view(request: Request, page: str):
    result_path = Path("data/result") / f"{page}.json"
    data = json.loads(result_path.read_text())
    return templates.TemplateResponse(
        request=request, name="result.html", context={
            "page": page,
            "title": data["title"],
            "html": data["html"],
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
    chunks, _restore_info = preprocess_split_html(data.page.text, title=data.page.title, size=4096)
    return templates.TemplateResponse(
        request=request, name="source.html", context={
            "data": data,
            "chunks": chunks,
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("jako.web.server:app", host="0.0.0.0", port=8000, reload=True)
