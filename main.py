
from datetime import datetime
from os import getenv
from typing import List, Optional
from db import get_db_connection

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="QM Feedback System")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates Konfiguration
templates = Jinja2Templates(directory="templates")

# --- Shared secret protection ---
SHARED_SECRET = getenv("SHARED_SECRET", "change-me")
EXEMPT_PATHS = {"/favicon.ico", "/health", "/robots.txt"}
EXEMPT_PREFIXES = ("/static",)


@app.middleware("http")
async def enforce_shared_secret(request: Request, call_next):
    path = request.url.path

    # Allow health checks and static assets without a token
    if path in EXEMPT_PATHS:
        if path == "/health":
            return PlainTextResponse("ok")
        return await call_next(request)
    if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
        return await call_next(request)

    token_cookie = request.cookies.get("shared_secret")
    token_query = request.query_params.get("key")

    if token_cookie == SHARED_SECRET:
        return await call_next(request)

    if token_query == SHARED_SECRET:
        if request.method.upper() == "GET":
            cleaned_url = request.url.replace(query=None)
            response = RedirectResponse(url=str(cleaned_url), status_code=303)
            response.set_cookie(
                "shared_secret",
                SHARED_SECRET,
                httponly=True,
                secure=True,
                samesite="lax",
            )
            return response

        response = await call_next(request)
        response.set_cookie(
            "shared_secret",
            SHARED_SECRET,
            httponly=True,
            secure=True,
            samesite="lax",
        )
        return response

    return PlainTextResponse("Zugriff verweigert, bitte verwenden Sie den korrekten Schlüssel.", status_code=403)


# --- RMZ Daten aus CSV laden ---
import csv

def load_rmz_list():
    rmz_list = []
    try:
        with open("RMZ.csv", "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader, None)  # skip header
            for row in reader:
                if row and len(row) >= 2:
                    rmz_list.append(f"{row[0]} - {row[1]}")
    except Exception as e:
        print(f"Error loading RMZ list: {e}")
    return rmz_list

RMZ_LISTEN = load_rmz_list()

def load_funkrufnamen():
    funkrufnamen = []
    try:
        with open("Funkrufnamen.csv", "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile, delimiter=";")
            for row in reader:
                rufname = (row.get("Rufname") or "").strip()
                opta = (row.get("OPTA-Rufname") or "").strip()
                if rufname:
                    funkrufnamen.append(
                        {
                            "rufname": rufname,
                            "opta": opta or rufname,
                        }
                    )
    except Exception as e:
        print(f"Error loading Funkrufnamen: {e}")

    if not funkrufnamen:
        funkrufnamen = [
            {"rufname": "MISSING", "opta": "Fehlend"},
        ]
    return funkrufnamen

FUNKRUFNAMEN = load_funkrufnamen()
    

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


# --- Rechtliches ---
@app.get("/impressum", response_class=HTMLResponse)
async def impressum(request: Request):
    return templates.TemplateResponse("impressum.html", {"request": request})


@app.get("/datenschutz", response_class=HTMLResponse)
async def datenschutz(request: Request):
    return templates.TemplateResponse("datenschutz.html", {"request": request})

@app.get('/robots.txt', response_class=PlainTextResponse, include_in_schema=False)
async def robots():
    data = """User-agent: *\nDisallow: /"""
    return data

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


    # Speichern in Datenbank
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rd_feedback (
                id SERIAL PRIMARY KEY,
                nk_nummer VARCHAR(20),
                rettungsmittel VARCHAR(50),
                stichwort_check VARCHAR(100),
                kommentar TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            "INSERT INTO rd_feedback (nk_nummer, rettungsmittel, stichwort_check, kommentar) VALUES (%s, %s, %s, %s)",
            (nk_nummer, rettungsmittel, stichwort_check, kommentar)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB error (RD): {e}")

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



# --- Updated Klinik Submit with RMC fields ---
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
    rmc_bewusstsein: str = Form(...),
    rmc_atmung: str = Form(...),
    rmc_kreislauf: str = Form(...),
    rmc_verletzung: str = Form(...),
    rmc_neurologie: str = Form(...),
    rmc_schmerz: str = Form(...),
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

    # Extract RMZ code (first column of RMZ.csv, before ' - ')
    rmz_code = rmz.split(' - ')[0] if ' - ' in rmz else rmz

    # Build 9-digit RMC code: 3 digits for RMZ code, 6 digits for feedback
    rmc_code = f"{rmz_code:0>3}{rmc_bewusstsein}{rmc_atmung}{rmc_kreislauf}{rmc_verletzung}{rmc_neurologie}{rmc_schmerz}"

    diagnosen = [d for d in [icd_1, icd_2, icd_3] if d]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS klinik_feedback (
                id SERIAL PRIMARY KEY,
                auftragsnummer INTEGER,
                rmz VARCHAR(100),
                icds TEXT,
                mst VARCHAR(50),
                kommentar TEXT,
                rmc_code VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            "INSERT INTO klinik_feedback (auftragsnummer, rmz, icds, mst, kommentar, rmc_code) VALUES (%s, %s, %s, %s, %s, %s)",
            (int(auftragsnummer), rmz, ",".join(diagnosen), mst, kommentar, rmc_code)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB error (Klinik): {e}")

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


    # Speichern in Datenbank
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lst_feedback (
                id SERIAL PRIMARY KEY,
                nk_nummer VARCHAR(20),
                sna_anpassung VARCHAR(100),
                kommentar TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            "INSERT INTO lst_feedback (nk_nummer, sna_anpassung, kommentar) VALUES (%s, %s, %s)",
            (nk_nummer, sna_anpassung, kommentar)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB error (LST): {e}")

    return templates.TemplateResponse(
        "success.html", {"request": request, "source": "Leitstelle"}
    )
