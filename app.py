from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="SIGMA")

"""resolvendo o problema do diretorio 
__file__ -> nosso arquivo atual (main.py)
resolve() -> função que converte o caminho do nosso arquivo para diretorio para absoluto
parent -> sobe um nível de diretório para entender onde main.py está
"""
# com essas ponderações consideramos BASE_DIR como SIGMA-API
BASE_DIR = Path(__file__).resolve().parent

# public estará em SIGMA-API/public
PUBLIC = BASE_DIR / "public"

templates = Jinja2Templates(directory=PUBLIC)

@app.get("/", response_class=HTMLResponse)
async def index():
    # se o usuário não estiver logado redireciona para login
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    context = {"request": request, "titulo": "Login"}
    return templates.TemplateResponse("login.html", context)

# rodar a aplicação uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
    )