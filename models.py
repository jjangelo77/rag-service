from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Estrutura de dados que esperamos receber do n8n.
# O n8n deve preencher estes campos para solicitar um agendamento.
class AgendamentoPayload(BaseModel):
    """
    Define o corpo da requisição POST que o n8n envia para agendar um evento.
    """
    
    # Informações básicas do evento
    summary: str 
    description: Optional[str] = None
    
    # O email do usuário que será o organizador e dono do calendário.
    organizer_email: str
    
    # Tempo do evento. Assume-se formato ISO 8601 (ex: "2025-10-25T10:00:00")
    start_time: datetime
    end_time: datetime
    
    # Opcional: lista de emails de outros participantes
    attendee_emails: Optional[list[str]] = None

    # Opcional: ID da reunião de vídeo (ex: Google Meet, Zoom)
    conference_id: Optional[str] = None