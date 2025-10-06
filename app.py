from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette import status

app = FastAPI(title='SIGMA')
app.add_middleware(SessionMiddleware, secret_key="chave-secreta")

'''resolvendo o problema do diretorio 
__file__ -> nosso arquivo atual (main.py)
resolve() -> função que converte o caminho do nosso arquivo para diretorio para absoluto
parent -> sobe um nível de diretório para entender onde main.py está
'''
# com essas ponderações consideramos BASE_DIR como SIGMA-API
BASE_DIR = Path(__file__).resolve().parent

# public estará em SIGMA-API/public
PUBLIC = BASE_DIR / 'public'

templates = Jinja2Templates(directory=PUBLIC)

@app.get('/', response_class=HTMLResponse)
async def index():
    # se o usuário não estiver logado redireciona para login
    return RedirectResponse(url='/login')


@app.get('/login', response_class=HTMLResponse)
async def login(request: Request):
    context = {'request': request, 'titulo': 'Login'}
    return templates.TemplateResponse('login.html', context)

@app.post('/auth/login')
async def login(request: Request, email: str = Form(...), password: str = Form(...), remember: bool = Form(False)):

    senhas = {'aluno': 'aluno',
             'professor': 'professor',
             'seguranca': 'seguranca',
             'admin': 'admin'
             }
    
    destinos = {'aluno': '/painel/aluno',
               'professor': '/painel/professor',
               'seguranca': '/painel/seguranca',
               'admin': '/painel/admin'
               }

    if email in senhas:
        if password == senhas[email]:
            role = email
            destino = f'{destinos[email]}'
    else:
        # credenciais inválidas → re-renderiza o template com erro (aqui sim usa request/context)
        ctx = {"request": request, "titulo": "Login", "erro": "Credenciais inválidas."}
        return templates.TemplateResponse("login.html", ctx, status_code=status.HTTP_401_UNAUTHORIZED)
    
    # grava sessão (opcional, mas útil para as telas protegidas)
    request.session["user_id"] = email
    request.session["role"] = role
    request.session["remember"] = bool(remember)

    return RedirectResponse(url=destino, status_code=status.HTTP_302_FOUND)


@app.get("/painel/aluno", response_class=HTMLResponse)
async def painel_aluno(request: Request):
    context = {'request': request, 'titulo': 'Aluno'}
    return templates.TemplateResponse('/aluno/aluno.html', context)

@app.get("/painel/professor", response_class=HTMLResponse)
async def painel_prof(request: Request):
    context = {'request': request, 'titulo': 'Professor'}
    return templates.TemplateResponse('/professor/professor.html', context)

@app.get("/painel/seguranca", response_class=HTMLResponse)
async def painel_seg(request: Request):
    context = {'request': request, 'titulo': 'Seguranca'}
    return templates.TemplateResponse('/seguranca/seguranca.html', context)

@app.get("/painel/admin", response_class=HTMLResponse)
async def painel_admin(request: Request):
    context = {'request': request, 'titulo': 'Admin'}
    return templates.TemplateResponse('/admin/admin.html', context)


# rodar a aplicação uvicorn
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'app:app',
        host='127.0.0.1',
        port=8001,
        reload=True,
    )