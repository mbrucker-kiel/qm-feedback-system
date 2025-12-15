from typing import List, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="QM Feedback System")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates Konfiguration
templates = Jinja2Templates(directory="templates")

# --- Dummy Daten (Später aus DB oder Config) ---
RMZ_LISTEN = ["RMZ Liste 1", "RMZ Liste 2", "RMZ Liste 3"]  # Hier echte Listen ergänzen


def load_icd_codes():
    codes = []
    try:
        with open("icd10gm2025syst_kodes.txt", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) >= 9:
                    codes.append(f"{parts[6]} - {parts[8]}")
    except Exception as e:
        print(f"Error loading ICD codes: {e}")
    return codes


ICD_CODES = load_icd_codes()
MST_GRUPPEN = [
    "Rot (Sofort)",
    "Orange (Sehr dringend)",
    "Gelb (Dringend)",
    "Grün (Normal)",
    "Blau (Nicht dringend)",
]

# --- Routen ---


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# --- Rettungsdienst (RD) ---
@app.get("/rd", response_class=HTMLResponse)
async def form_rd(request: Request):
    return templates.TemplateResponse("rd.html", {"request": request})


@app.post("/rd/submit", response_class=HTMLResponse)
async def submit_rd(
    request: Request,
    nk_nummer: int = Form(...),
    rettungsmittel: str = Form(...),
    stichwort_check: str = Form(...),
    kommentar: Optional[str] = Form(None),
):
    # HIER: Speichern in Datenbank
    print(
        f"RD FEEDBACK: NK={nk_nummer}, RM={rettungsmittel}, Check={stichwort_check}, Kom={kommentar}"
    )

    return templates.TemplateResponse(
        "success.html", {"request": request, "source": "Rettungsdienst"}
    )


# --- Klinik ---
@app.get("/klinik", response_class=HTMLResponse)
async def form_klinik(request: Request):
    return templates.TemplateResponse(
        "klinik.html",
        {
            "request": request,
            "rmz_options": RMZ_LISTEN,
            "icd_options": ICD_CODES,
            "mst_options": MST_GRUPPEN,
        },
    )


@app.post("/klinik/submit", response_class=HTMLResponse)
async def submit_klinik(
    request: Request,
    auftragsnummer: int = Form(...),
    rmz: str = Form(...),
    icd_1: str = Form(...),
    icd_2: Optional[str] = Form(None),
    icd_3: Optional[str] = Form(None),
    mst: str = Form(...),
    kommentar: Optional[str] = Form(None),
):
    # HIER: Speichern in Datenbank
    diagnosen = [d for d in [icd_1, icd_2, icd_3] if d]
    print(
        f"KLINIK FEEDBACK: AN={auftragsnummer}, RMZ={rmz}, ICDs={diagnosen}, MST={mst}"
    )

    return templates.TemplateResponse(
        "success.html", {"request": request, "source": "Klinik"}
    )


# --- Leitstelle (LST) ---
@app.get("/leitstelle", response_class=HTMLResponse)
async def form_lst(request: Request):
    return templates.TemplateResponse("lst.html", {"request": request})


@app.post("/leitstelle/submit", response_class=HTMLResponse)
async def submit_lst(
    request: Request,
    nk_nummer: int = Form(...),
    sna_anpassung: str = Form(...),
    kommentar: Optional[str] = Form(None),
):
    # HIER: Speichern in Datenbank
    print(f"LST FEEDBACK: NK={nk_nummer}, SNA={sna_anpassung}")

    return templates.TemplateResponse(
        "success.html", {"request": request, "source": "Leitstelle"}
    )
    return templates.TemplateResponse(
        "success.html", {"request": request, "source": "Leitstelle"}
    )
