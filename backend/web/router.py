from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/apartments/{apartment_id}", response_class=HTMLResponse)
async def apartment_detail(request: Request, apartment_id: int):
    return templates.TemplateResponse(
        "apartment.html", {"request": request, "apartment_id": apartment_id}
    )


@router.get("/competitor", response_class=HTMLResponse)
async def competitor(request: Request):
    return templates.TemplateResponse("competitor.html", {"request": request})


@router.get("/sessions", response_class=HTMLResponse)
async def sessions(request: Request):
    return templates.TemplateResponse("sessions.html", {"request": request})


@router.get("/events", response_class=HTMLResponse)
async def events(request: Request):
    return templates.TemplateResponse("events.html", {"request": request})
