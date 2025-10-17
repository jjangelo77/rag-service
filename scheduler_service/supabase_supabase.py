from supabase import create_client, Client
from typing import Optional, Dict, Any
import os # ESSENCIAL
from datetime import datetime
import json
from dotenv import load_dotenv

# Carrega variáveis de ambiente, garantindo que o get_supabase_client funcione 
# mesmo se chamado isoladamente, embora main.py já faça isso.
load_dotenv() 

# --- Cliente de Conexão ---
def get_supabase_client() -> Client:
    url: str = os.getenv("SUPABASE_URL")
    key: str = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise Exception("Credenciais Supabase (SUPABASE_URL/SUPABASE_KEY) não estão definidas no ambiente.")
        
    return create_client(url, key)

# --- Função de Busca de Email (Vendedor) ---
def get_lifeplanner_email(lifeplanner_id: str) -> Optional[str]:
    """Busca o email de calendário do Life Planner na tabela 'life_planners' (Escalável)."""
    supabase = get_supabase_client()
    try:
        # Busca na tabela 'life_planners' usando o ID do Vendedor
        response = supabase.table("life_planners").select("email_calendario").eq("id", lifeplanner_id).limit(1).execute()
        
        data = response.data
        if data and len(data) > 0 and data[0].get("email_calendario"):
            return data[0]["email_calendario"]
        
        # Fallback de segurança
        print(f"ALERTA: ID do Life Planner '{lifeplanner_id}' não encontrado na tabela 'life_planners'. Usando Fallback.")
        return "jjsales003@gmail.com" 
        
    except Exception as e:
        print(f"ERRO SUPABASE: Falha ao buscar email para {lifeplanner_id}: {e}")
        return "jjsales003@gmail.com"

# --- Função de Salvamento (Agendamentos Ativos) ---
def save_agendamento(agendamento_data: Dict[str, Any], event_id: str, event_link: str) -> None:
    """Salva os dados do agendamento finalizado na tabela agendamentos_ativos."""
    supabase = get_supabase_client()
    
    payload = {
        # O 'cliente_id' do payload é o 'id_lifeplanner' na tabela
        "id_lifeplanner": agendamento_data["cliente_id"],         
        "cliente_celular": agendamento_data["cliente_celular"],   
        "summary": agendamento_data["summary"],
        "description": agendamento_data["description"],
        "start_time": agendamento_data["start_time"].isoformat(), 
        "end_time": agendamento_data["end_time"].isoformat(),
        "event_ide_google": event_id,
        "status": "AGENDADO", 
    }
    
    try:
        supabase.table("agendamentos_ativos").insert(payload).execute()
        
    except Exception as e:
        print("ERRO CRÍTICO: Falha ao salvar no Supabase 'agendamentos_ativos'.")
        print("Payload Enviado:", json.dumps(payload, indent=2))
        print(f"Erro da API Supabase: {e}")