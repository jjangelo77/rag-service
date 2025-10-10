from typing import Optional, Dict, Any

# ======================================================================
# ATENÇÃO: ESTE É UM CLIENTE MOCK (FALSO)
# Para um ambiente de produção, esta lógica precisaria ser substituída
# por uma conexão real com o Supabase usando a biblioteca 'supabase-py'.
# ======================================================================

def get_google_refresh_token(user_id: str) -> Optional[str]:
    """
    Simula a recuperação de um refresh token do Google Calendar
    associado a um usuário no banco de dados.
    """
    print(f"[MOCK DB] Recuperando refresh token para user_id: {user_id}...")
    
    # Em um ambiente real, você consultaria o Supabase aqui.
    # Exemplo: client.table('users').select('google_refresh_token').eq('id', user_id).execute()
    
    # Retorna um token mock apenas para permitir que o servidor inicie e a lógica de agendamento prossiga.
    # O valor 'None' simularia um usuário não autenticado.
    if user_id and user_id != "unauthenticated_user":
        return "MOCK_VALID_REFRESH_TOKEN"
    return None

def insert_agendamento_record(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simula a inserção de um registro de agendamento no banco de dados.
    """
    print("[MOCK DB] Inserindo novo registro de agendamento no banco de dados...")
    print(f"[MOCK DB] Dados a serem inseridos: {event_data.get('summary')}")
    
    # Em um ambiente real, você inseriria o registro no Supabase aqui.
    # Exemplo: client.table('agendamentos').insert(event_data).execute()
    
    return {"success": True, "db_record_id": "mock-record-12345"}
