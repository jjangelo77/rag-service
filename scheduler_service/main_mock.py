from fastapi import FastAPI, APIRouter, HTTPException, Body
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional

# --- FastAPI & Router ---
app = FastAPI()
router = APIRouter(prefix="/agendar")

# --- Mock global ---
EVENT_COUNTER = 1
MOCK_AGENDAMENTOS = []

# --- Timezone e regras de horário ---
from zoneinfo import ZoneInfo
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

# --- Modelos ---
class AgendamentoPayload(BaseModel):
    summary: str
    description: str
    start_time: datetime
    end_time: datetime
    attendee_emails: List[str]
    organizer_email: str

# --- Funções utilitárias ---
def get_business_window_for_date(d: date) -> Optional[Tuple[datetime, datetime]]:
    rule = BUSINESS_HOURS.get(d.weekday())
    if not rule:
        return None
    start_str, end_str = rule
    start_dt = datetime.combine(d, datetime.strptime(start_str, "%H:%M").time()).replace(tzinfo=TZ)
    end_dt = datetime.combine(d, datetime.strptime(end_str, "%H:%M").time()).replace(tzinfo=TZ)
    return start_dt, end_dt

def generate_slots_for_day(d: date) -> List[Tuple[datetime, datetime]]:
    window = get_business_window_for_date(d)
    if not window:
        return []
    start_dt, end_dt = window
    slots = []
    cur = start_dt
    while (cur + timedelta(minutes=60)) <= end_dt:
        slots.append((cur, cur + timedelta(minutes=60)))
        cur += timedelta(minutes=60)
    if (end_dt - cur) >= timedelta(minutes=50):
        slots.append((cur, cur + timedelta(minutes=50)))
    return slots

# --- Endpoints ---
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

@router.post("/")
def schedule_event(payload: AgendamentoPayload):
    global EVENT_COUNTER
    event_id = f"mock_event_{EVENT_COUNTER}"
    EVENT_COUNTER += 1
    MOCK_AGENDAMENTOS.append({
        "event_id_google": event_id,
        "summary": payload.summary,
        "description": payload.description,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
        "attendee_emails": payload.attendee_emails,
        "organizer_email": payload.organizer_email,
        "status": "scheduled",
        "id_lifeplanner": "mock_lp_1",
        "cliente_celular": "123456789"
    })
    return {"status": "success", "event_id": event_id, "event_link": f"https://mockcalendar.com/{event_id}"}

@router.post("/reagendar/")
def reschedule_event(payload: dict = Body(...)):
    ag = next((a for a in MOCK_AGENDAMENTOS if a["id_lifeplanner"] == payload.get("id_lifeplanner")
               and a["cliente_celular"] == payload.get("cliente_celular") and a["status"] == "scheduled"), None)
    if not ag:
        raise HTTPException(404, "Agendamento não encontrado")
    ag["start_time"] = payload.get("new_start_time")
    ag["end_time"] = payload.get("new_end_time")
    return {"status": "success", "event_id": ag["event_id_google"], "event_link": f"https://mockcalendar.com/{ag['event_id_google']}"}

@router.post("/cancelar/")
def cancel_event(payload: dict = Body(...)):
    ag = next((a for a in MOCK_AGENDAMENTOS if a["id_lifeplanner"] == payload.get("id_lifeplanner")
               and a["cliente_celular"] == payload.get("cliente_celular") and a["status"] == "scheduled"), None)
    if not ag:
        raise HTTPException(404, "Agendamento não encontrado")
    ag["status"] = "canceled"
    return {"status": "success", "event_id": ag["event_id_google"]}

# --- Inclui router ---
app.include_router(router)
