from dotenv import load_dotenv
import os
from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Optional
from fastapi import FastAPI, APIRouter, HTTPException, Body
from pydantic import BaseModel
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo

# 🟢 Importa o router do scheduler_service
from scheduler_service.agendar import router as scheduler_router


# --- Carrega variáveis do .env ---
load_dotenv()
print("=== DEBUG VARIÁVEIS ===")
print("CWD:", os.getcwd())
print("GOOGLE_SERVICE_ACCOUNT_FILE:", os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"))

# --- Inicializa FastAPI ---
app = FastAPI()
# 🟢 Inclui as rotas do serviço de agendamento
app.include_router(scheduler_router, prefix="/agendar", tags=["Agendamentos"])


# --- Modelo de payload ---
class AgendamentoPayload(BaseModel):
    summary: str
    description: str
    start_time: datetime
    end_time: datetime
    attendee_emails: List[str]
    organizer_email: str

# --- Função para criar o serviço do Google Calendar ---
def get_calendar_service():
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")

    # Corrige barras no Windows
    if service_account_file:
        service_account_file = service_account_file.replace("\\", "/")

    # Prints de debug
    print("🔎 Verificando arquivo:", service_account_file)
    print("✅ Existe?:", os.path.exists(service_account_file))

    if not service_account_file or not os.path.exists(service_account_file):
        raise HTTPException(
            status_code=500,
            detail="Arquivo de Service Account não encontrado. Defina GOOGLE_SERVICE_ACCOUNT_FILE no .env."
        )

    creds = Credentials.from_service_account_file(
        service_account_file,
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=creds)
    return service

# --- Configuração de timezone e regras de negócio ---
TIMEZONE = "America/Sao_Paulo"
TZ = ZoneInfo(TIMEZONE)

BUSINESS_HOURS = {
    0: ("13:00", "18:00"),  # Segunda
    1: ("11:00", "18:00"),  # Terça
    2: ("11:00", "18:00"),  # Quarta
    3: ("11:00", "18:00"),  # Quinta
    4: ("11:00", "13:00"),  # Sexta
    5: None,                # Sábado
    6: None,                # Domingo
}

# --- Funções auxiliares ---
try:
    from dateutil.parser import isoparse
except Exception:
    def isoparse(s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

def get_business_window_for_date(d: date) -> Optional[Tuple[datetime, datetime]]:
    rule = BUSINESS_HOURS.get(d.weekday())
    if not rule:
        return None
    start_str, end_str = rule
    start_t = datetime.strptime(start_str, "%H:%M").time()
    end_t = datetime.strptime(end_str, "%H:%M").time()
    start_dt = datetime.combine(d, start_t).replace(tzinfo=TZ)
    end_dt = datetime.combine(d, end_t).replace(tzinfo=TZ)
    return start_dt, end_dt

def is_holiday(d: date) -> bool:
    try:
        from scheduler_service.supabase_client import get_holidays_for_date
        return get_holidays_for_date(d)
    except Exception:
        LOCAL_HOLIDAYS = set()
        return d in LOCAL_HOLIDAYS

def get_existing_events_for_day(d: date) -> List[Tuple[datetime, datetime]]:
    window = get_business_window_for_date(d)
    if not window:
        return []
    start_dt, end_dt = window
    service = get_calendar_service()
    events_res = service.events().list(
        calendarId="primary",
        timeMin=start_dt.isoformat(),
        timeMax=end_dt.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    items = events_res.get("items", [])
    intervals = []
    for ev in items:
        s = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        e = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
        if not s or not e:
            continue
        sdt = isoparse(s).astimezone(TZ)
        edt = isoparse(e).astimezone(TZ)
        intervals.append((sdt, edt))
    return intervals

def merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = []
    cur_s, cur_e = intervals[0]
    for s, e in intervals[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged

def generate_slots_for_day(d: date) -> List[Tuple[datetime, datetime]]:
    if is_holiday(d):
        return []
    window = get_business_window_for_date(d)
    if not window:
        return []
    start_dt, end_dt = window
    busy = get_existing_events_for_day(d)
    busy = merge_intervals(busy)

    free_intervals = []
    cur = start_dt
    for b_s, b_e in busy:
        if b_s > cur:
            free_intervals.append((cur, b_s))
        cur = max(cur, b_e)
    if cur < end_dt:
        free_intervals.append((cur, end_dt))

    slots = []
    for f_s, f_e in free_intervals:
        iter_start = f_s
        while (iter_start + timedelta(minutes=60)) <= f_e:
            slots.append((iter_start, iter_start + timedelta(minutes=60)))
            iter_start += timedelta(minutes=60)
        if (f_e - iter_start) >= timedelta(minutes=50):
            slots.append((iter_start, iter_start + timedelta(minutes=50)))
    return slots

# --- Endpoint para consultar slots ---
@router.post("/slots/")
def available_slots(payload: dict = Body(...)):
    date_str = payload.get("date")
    if not date_str:
        raise HTTPException(status_code=400, detail="Campo 'date' obrigatório (YYYY-MM-DD)")
    try:
        d = date.fromisoformat(date_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD")
    slots = generate_slots_for_day(d)
    return {"date": date_str, "slots": [{"start": s.isoformat(), "end": e.isoformat()} for s, e in slots]}

# --- Endpoint para criar agendamento ---
@router.post("/")
def schedule_event(payload: AgendamentoPayload):
    try:
        service = get_calendar_service()
        event = {
            "summary": payload.summary,
            "description": payload.description,
            "start": {"dateTime": payload.start_time.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": payload.end_time.isoformat(), "timeZone": TIMEZONE},
            "attendees": [{"email": email} for email in payload.attendee_emails],
            "organizer": {"email": payload.organizer_email},
            "reminders": {"useDefault": True},
        }
        created_event = service.events().insert(calendarId="primary", body=event).execute()
        return {
            "status": "success",
            "event_id": created_event.get("id"),
            "event_link": created_event.get("htmlLink")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao agendar: {e}")

# --- Endpoint para reagendar ---
@router.post("/reagendar/")
def reschedule_event(payload: dict = Body(...)):
    id_lp = payload.get("id_lifeplanner")
    celular = payload.get("cliente_celular")
    new_start_str = payload.get("new_start_time")
    new_end_str = payload.get("new_end_time")
    if not all([id_lp, celular, new_start_str, new_end_str]):
        raise HTTPException(400, "Campos obrigatórios: id_lifeplanner, cliente_celular, new_start_time, new_end_time")
    
    res = supabase.table("agendamentos") \
        .select("*") \
        .eq("id_lifeplanner", id_lp) \
        .eq("cliente_celular", celular) \
        .eq("status", "scheduled") \
        .execute()
    if not res.data:
        raise HTTPException(404, "Agendamento não encontrado")
    ag = res.data[0]

    try:
        service = get_calendar_service()
        event_id = ag["event_id_google"]
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        event["start"]["dateTime"] = new_start_str
        event["end"]["dateTime"] = new_end_str
        updated_event = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()

        supabase.table("agendamentos").update({
            "start_time": new_start_str,
            "end_time": new_end_str
        }).eq("id", ag["id"]).execute()

        return {"status": "success", "event_id": event_id, "event_link": updated_event.get("htmlLink")}

    except Exception as e:
        raise HTTPException(500, f"Falha ao reagendar: {e}")

# --- Endpoint para cancelar ---
@router.post("/cancelar/")
def cancel_event(payload: dict = Body(...)):
    id_lp = payload.get("id_lifeplanner")
    celular = payload.get("cliente_celular")
    if not id_lp or not celular:
        raise HTTPException(400, "Campos obrigatórios: id_lifeplanner, cliente_celular")

    res = supabase.table("agendamentos") \
        .select("*") \
        .eq("id_lifeplanner", id_lp) \
        .eq("cliente_celular", celular) \
        .eq("status", "scheduled") \
        .execute()
    if not res.data:
        raise HTTPException(404, "Agendamento não encontrado")
    ag = res.data[0]

    try:
        service = get_calendar_service()
        event_id = ag["event_id_google"]
        service.events().delete(calendarId="primary", eventId=event_id).execute()

        supabase.table("agendamentos").update({
            "status": "canceled"
        }).eq("id", ag["id"]).execute()

        return {"status": "success", "event_id": event_id}
    except Exception as e:
        raise HTTPException(500, f"Falha ao cancelar: {e}")

# --- Inclui router no app ---
app.include_router(router)
