from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="QM Feedback System")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates Konfiguration
templates = Jinja2Templates(directory="templates")


# --- RMZ Daten aus CSV laden ---
import csv

def load_rmz_list():
    rmz_list = []
    try:
        with open("RMZ.csv", "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:
                    rmz_list.append(row[0])
    except Exception as e:
        print(f"Error loading RMZ list: {e}")
    return rmz_list

RMZ_LISTEN = load_rmz_list()

FUNKRUFNAMEN = ["10-83-01", "10-83-02", "10-82-01"]


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
    return templates.TemplateResponse(
        "rd.html", {"request": request, "funkrufnamen": FUNKRUFNAMEN}
    )


@app.post("/rd/submit", response_class=HTMLResponse)
async def submit_rd(
    request: Request,
    nk_date: str = Form(...),
    nk_sequence: str = Form(...),
    rettungsmittel: str = Form(...),
    stichwort_check: str = Form(...),
    kommentar: Optional[str] = Form(None),
):
    # Validierung NK-Nummer
    if len(nk_sequence) != 5 or not nk_sequence.isdigit():
        return templates.TemplateResponse(
            "rd.html",
            {
                "request": request,
                "funkrufnamen": FUNKRUFNAMEN,
                "error": "Die laufende Nummer muss genau 5 Ziffern enthalten.",
            },
        )

    if len(nk_date) != 6 or not nk_date.isdigit():
        return templates.TemplateResponse(
            "rd.html",
            {
                "request": request,
                "funkrufnamen": FUNKRUFNAMEN,
                "error": "Das Datum muss im Format YYMMDD (6 Ziffern) sein.",
            },
        )

    if int(nk_date[:2]) < 25:
        return templates.TemplateResponse(
            "rd.html",
            {
                "request": request,
                "funkrufnamen": FUNKRUFNAMEN,
                "error": "Das Jahr muss 25 oder höher sein.",
            },
        )

    try:
        input_date = datetime.strptime(nk_date, "%y%m%d").date()
        if input_date > datetime.now().date():
            return templates.TemplateResponse(
                "rd.html",
                {
                    "request": request,
                    "funkrufnamen": FUNKRUFNAMEN,
                    "error": "Das Datum darf nicht in der Zukunft liegen.",
                },
            )
    except ValueError:
        return templates.TemplateResponse(
            "rd.html",
            {
                "request": request,
                "funkrufnamen": FUNKRUFNAMEN,
                "error": "Ungültiges Datum (z.B. 30. Februar).",
            },
        )

    # Formatierung: NK YYMMDD 12345
    nk_nummer = f"NK {nk_date} {nk_sequence}"

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
    auftragsnummer: str = Form(...),
    rmz: str = Form(...),
    icd_1: str = Form(...),
    icd_2: Optional[str] = Form(None),
    icd_3: Optional[str] = Form(None),
    mst: str = Form(...),
    kommentar: Optional[str] = Form(None),
):
    if len(auftragsnummer) > 6 or not auftragsnummer.isdigit():
        return templates.TemplateResponse(
            "klinik.html",
            {
                "request": request,
                "rmz_options": RMZ_LISTEN,
                "icd_options": ICD_CODES,
                "mst_options": MST_GRUPPEN,
                "error": "Die Auftragsnummer darf maximal 6 Ziffern enthalten.",
            },
        )

    # HIER: Speichern in Datenbank
    diagnosen = [d for d in [icd_1, icd_2, icd_3] if d]
    auftragsnummer_int = int(auftragsnummer)
    print(
        f"KLINIK FEEDBACK: AN={auftragsnummer_int}, RMZ={rmz}, ICDs={diagnosen}, MST={mst}"
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
    nk_date: str = Form(...),
    nk_sequence: str = Form(...),
    sna_anpassung: str = Form(...),
    kommentar: Optional[str] = Form(None),
):
    # Validierung NK-Nummer
    if len(nk_sequence) != 5 or not nk_sequence.isdigit():
        return templates.TemplateResponse(
            "lst.html",
            {
                "request": request,
                "error": "Die laufende Nummer muss genau 5 Ziffern enthalten.",
            },
        )

    if len(nk_date) != 6 or not nk_date.isdigit():
        return templates.TemplateResponse(
            "lst.html",
            {
                "request": request,
                "error": "Das Datum muss im Format YYMMDD (6 Ziffern) sein.",
            },
        )

    if int(nk_date[:2]) < 25:
        return templates.TemplateResponse(
            "lst.html",
            {
                "request": request,
                "error": "Das Jahr muss 25 oder höher sein.",
            },
        )

    try:
        input_date = datetime.strptime(nk_date, "%y%m%d").date()
        if input_date > datetime.now().date():
            return templates.TemplateResponse(
                "lst.html",
                {
                    "request": request,
                    "error": "Das Datum darf nicht in der Zukunft liegen.",
                },
            )
    except ValueError:
        return templates.TemplateResponse(
            "lst.html",
            {
                "request": request,
                "error": "Ungültiges Datum (z.B. 30. Februar).",
            },
        )

    # Formatierung: NK YYMMDD 12345
    nk_nummer = f"NK {nk_date} {nk_sequence}"

    # HIER: Speichern in Datenbank
    print(f"LST FEEDBACK: NK={nk_nummer}, SNA={sna_anpassung}")

    return templates.TemplateResponse(
        "success.html", {"request": request, "source": "Leitstelle"}
    )
