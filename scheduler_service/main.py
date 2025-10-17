from dotenv import load_dotenv
import os
from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Optional
from fastapi import FastAPI, APIRouter, HTTPException, Body
from pydantic import BaseModel
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo

# 🟢 Importa as funções de Supabase e a função de cliente Supabase
# DEPOIS:
from supabase_supabase import get_lifeplanner_email, save_agendamento, get_supabase_client

# --- Carrega variáveis do .env ---
load_dotenv()
print("=== DEBUG VARIÁVEIS ===")
print("CWD:", os.getcwd())
print("GOOGLE_SERVICE_ACCOUNT_FILE:", os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"))

# --- Inicializa FastAPI e Router ---
app = FastAPI()
# Define o router para as rotas do serviço de agendamento (necessário para os @router.post abaixo)
router = APIRouter() 
# A linha abaixo deve ser corrigida ou removida se os endpoints estiverem neste arquivo:
# from scheduler_service.agendar import router as scheduler_router 
# app.include_router(scheduler_router, prefix="/agendar", tags=["Agendamentos"])

# --- Modelo de payload CORRIGIDO E ESCALÁVEL ---
class AgendamentoPayload(BaseModel):
    summary: str
    description: str
    start_time: datetime
    end_time: datetime
    attendee_emails: List[str]
    organizer_email: Optional[str] = None # Tornamos opcional, pois buscaremos via ID
    cliente_id: str # NOVO: ID DO LIFE PLANNER (VENDEDOR) - CRÍTICO PARA ESCALABILIDADE
    cliente_celular: Optional[str] = None # NOVO: Celular do Consumidor Final - CRÍTICO PARA SALVAMENTO


# --- Configuração de timezone e regras de negócio ---
TIMEZONE = "America/Sao_Paulo"
TZ = ZoneInfo(TIMEZONE)

BUSINESS_HOURS = {
    0: ("13:00", "18:00"),# Segunda
    1: ("11:00", "18:00"),# Terça
    2: ("11:00", "18:00"),# Quarta
    3: ("11:00", "18:00"),# Quinta
    4: ("11:00", "13:00"),# Sexta
    5: None,# Sábado
    6: None,# Domingo
}


# --- Função para criar o serviço do Google Calendar ---
def get_calendar_service():
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")

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

# --- Funções auxiliares (Sem alteração) ---
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
        # Nota: Seu código original chamava 'scheduler_service.supabase_client'. 
        # Esta lógica deve ser movida para o 'supabase_supabase.py' ou removida se não for usada.
        # Por simplicidade, mantemos o fallback:
        LOCAL_HOLIDAYS = set()
        return d in LOCAL_HOLIDAYS
    except Exception:
        LOCAL_HOLIDAYS = set()
        return d in LOCAL_HOLIDAYS

def get_existing_events_for_day(d: date) -> List[Tuple[datetime, datetime]]:
    # Esta função usa 'calendarId="primary"' - Isso deve ser revisado se houver múltiplos calendars de vendedores
    window = get_business_window_for_date(d)
    if not window:
        return []
    start_dt, end_dt = window
    service = get_calendar_service()
    events_res = service.events().list(
        calendarId="primary", # ATENÇÃO: Se for para vários LPs, este ID precisa ser dinâmico!
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

# --- Endpoint para consultar slots (Sem alteração) ---
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

# --- Endpoint para criar agendamento (CORRIGIDO PARA ESCALABILIDADE E SUPABASE) ---
@router.post("/")
def schedule_event(payload: AgendamentoPayload):
    try:
        # 1. DEFINE O CALENDÁRIO/ORGANIZADOR (LÓGICA ESCALÁVEL)
        calendar_id = payload.organizer_email # Prioridade 1: Tenta usar o email que o n8n envia
        
        if not calendar_id:
            # Prioridade 2: Busca na tabela 'life_planners' usando o ID do Vendedor
            calendar_id = get_lifeplanner_email(payload.cliente_id)
        
        # Fallback de Segurança
        if not calendar_id:
            calendar_id = "jjsales003@gmail.com" 

        # --- 2. GOOGLE CALENDAR (AGENDAMENTO) ---
        service = get_calendar_service()
        event = {
            "summary": payload.summary,
            "description": payload.description,
            "start": {"dateTime": payload.start_time.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": payload.end_time.isoformat(), "timeZone": TIMEZONE},
            "attendees": [{"email": email} for email in payload.attendee_emails],
            "organizer": {"email": calendar_id}, # Usa o email definido/buscado
            "reminders": {"useDefault": True},
        }
        
        # Cria o evento no calendário do Vendedor
        created_event = service.events().insert(
            calendarId=calendar_id, # CRÍTICO: Usa o ID do calendário/Vendedor DINÂMICO
            body=event
        ).execute()
        
        event_id = created_event.get("id")
        event_link = created_event.get("htmlLink")

        # --- 3. SUPABASE (SALVAMENTO) ---
        save_agendamento(payload.dict(), event_id, event_link)
        
        return {
            "status": "success",
            "event_id": event_id,
            "event_link": event_link
        }
        
    except Exception as e:
        print(f"ERRO FATAL DURANTE AGENDAMENTO: {e}")
        raise HTTPException(status_code=500, detail=f"Falha ao agendar: {e}")

# --- Endpoint para reagendar (CORRIGIDO para usar a nova função de cliente Supabase) ---
@router.post("/reagendar/")
def reschedule_event(payload: dict = Body(...)):
    db = get_supabase_client() # Obtém o cliente Supabase
    id_lp = payload.get("id_lifeplanner")
    celular = payload.get("cliente_celular")
    new_start_str = payload.get("new_start_time")
    new_end_str = payload.get("new_end_time")
    
    if not all([id_lp, celular, new_start_str, new_end_str]):
        raise HTTPException(400, "Campos obrigatórios: id_lifeplanner, cliente_celular, new_start_time, new_end_time")
    
    # Nota: Assumindo que a tabela ainda se chama "agendamentos" neste endpoint, mas o nome correto é "agendamentos_ativos"
    res = db.table("agendamentos") \
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
        
        # Busca o email do organizador (agora dinâmico)
        calendar_id = get_lifeplanner_email(id_lp)

        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        event["start"]["dateTime"] = new_start_str
        event["end"]["dateTime"] = new_end_str
        updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()

        db.table("agendamentos").update({
            "start_time": new_start_str,
            "end_time": new_end_str
        }).eq("id", ag["id"]).execute()

        return {"status": "success", "event_id": event_id, "event_link": updated_event.get("htmlLink")}

    except Exception as e:
        raise HTTPException(500, f"Falha ao reagendar: {e}")

# --- Endpoint para cancelar (CORRIGIDO para usar a nova função de cliente Supabase) ---
@router.post("/cancelar/")
def cancel_event(payload: dict = Body(...)):
    db = get_supabase_client() # Obtém o cliente Supabase
    id_lp = payload.get("id_lifeplanner")
    celular = payload.get("cliente_celular")
    
    if not id_lp or not celular:
        raise HTTPException(400, "Campos obrigatórios: id_lifeplanner, cliente_celular")

    res = db.table("agendamentos") \
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
        
        # Busca o email do organizador (agora dinâmico)
        calendar_id = get_lifeplanner_email(id_lp)

        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

        db.table("agendamentos").update({
            "status": "canceled"
        }).eq("id", ag["id"]).execute()

        return {"status": "success", "event_id": event_id}
    except Exception as e:
        raise HTTPException(500, f"Falha ao cancelar: {e}")

# --- Inclui router no app ---
app.include_router(router, prefix="/agendar") # Uso corrigido: inclui todas as rotas definidas acima
