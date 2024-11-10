import json
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")


templates = Jinja2Templates(directory=web_dir / "templates")


@app.get("/", response_class=HTMLResponse)
def list_view(request: Request):
    pages = []
    page_set = set()
    for f in os.listdir(Path("data/result")):
        page = f.replace(".json", "")
        pages.append({"page": page, "complete": True})
        page_set.add(page)

    for f in os.listdir(Path("data/checkpoint")):
        page = f.replace(".json", "")
        if page not in page_set:
            pages.append({"page": page, "complete": False})
            page_set.add(page)

    return templates.TemplateResponse(
        request=request, name="list.html", context={"pages": pages}
    )


@app.get("/result/{page}", response_class=HTMLResponse)
def result_view(request: Request, page: str, debug: bool = False):
    result_path = Path("data/result") / f"{page}.json"

    if debug or not result_path.exists():
        data = json.loads((Path("data/checkpoint") / f"{page}.json").read_text())
        return templates.TemplateResponse(
            request=request, name="debug.html", context=data
        )
    
    data = json.loads(result_path.read_text())
    return templates.TemplateResponse(
        request=request, name="result.html", context={
            "page": page,
            "title": data["title"],
            "html": data["html"],
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("jako.web.server:app", host="0.0.0.0", port=8000, reload=True)
