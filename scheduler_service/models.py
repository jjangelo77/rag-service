from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

# Define o schema de dados (Payload) que o endpoint /agendar espera receber.
# O Pydantic garante que os dados sejam validados automaticamente pelo FastAPI.
class AgendamentoPayload(BaseModel):
    """
    Estrutura de dados para agendar um evento no Google Calendar.
    """
    summary: str = Field(..., description="Título/Resumo do evento.")
    description: Optional[str] = Field(None, description="Descrição detalhada do evento.")
    
    # Datas e horários devem vir no formato ISO 8601 (ex: "2025-10-06T18:00:00")
    start_time: datetime = Field(..., description="Hora de início do evento (com timezone, se aplicável).")
    end_time: datetime = Field(..., description="Hora de término do evento (com timezone, se aplicável).")
    
    organizer_email: str = Field(..., description="Email do organizador do calendário.")
    attendee_emails: List[str] = Field(default_factory=list, description="Lista de emails dos participantes (opcional).")

    class Config:
        # Permite que o Pydantic use objetos datetime corretamente
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }