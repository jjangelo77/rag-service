# -*- coding: utf-8 -*-
# Este script constrói a URL de autorização manualmente para garantir que o 
# 'redirect_uri' esteja sempre presente, e então troca o código pelo token.

import os
import sys
import requests
from urllib.parse import urlencode

# --- ATUALIZE COM SUAS CREDENCIAIS ---
import os
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

# ------------------------------------

# A porta e URI devem corresponder EXATAMENTE ao que está no Google Cloud Console
PORTA = 8888
REDIRECT_URI = f"http://127.0.0.1:{PORTA}"

# Escopos do Google Calendar. Use estes escopos para a API do Google Calendar.
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar'
]

def exchange_code_for_token(code):
    """Troca o código de autorização pelo Access Token e Refresh Token."""
    print("\n--- PASSO 2: TROCANDO CÓDIGO POR TOKENS (POST REQUEST) ---")
    
    if "SEU_CLIENT_ID" in CLIENT_ID or "SEU_CLIENT_SECRET" in CLIENT_SECRET:
        print("🚨 ERRO: Por favor, substitua 'SEU_CLIENT_ID_DO_CLIENTE_WEB' e 'SEU_CLIENT_SECRET_DO_CLIENTE_WEB' pelas suas credenciais.")
        return
        
    token_url = "https://oauth2.googleapis.com/token"
    
    payload = {
        'code': code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status() # Lança um erro para códigos de status HTTP ruins
        
        tokens = response.json()
        
        refresh_token = tokens.get("refresh_token")
        
        if refresh_token:
            print("\n✅ REFRESH TOKEN OBTIDO COM SUCESSO!\n")
            print("=" * 60)
            print(f"REFRESH TOKEN: {refresh_token}")
            print("=" * 60)
            print("\n🚨 GUARDE ESTE TOKEN! Ele tem as permissões permanentes que você precisava.")
        else:
            print("\n❌ Não foi possível obter o Refresh Token.")
            print("MOTIVO PROVÁVEL: O Google só o envia uma vez. Tente revogar o acesso ANTES de rodar o script novamente.")
        
        return tokens

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Erro ao trocar código por tokens: {e}", file=sys.stderr)
        try:
            print("Resposta JSON de Erro do Google:", response.json(), file=sys.stderr)
        except:
            pass
        return None

def main():
    
    # Parâmetros necessários para a URL de autorização
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,             # OMITIDO na tentativa anterior, agora é OBRIGATÓRIO!
        'response_type': 'code',                  # Estamos pedindo um código para ser trocado
        'scope': ' '.join(SCOPES),                # Lista de escopos separada por espaço
        'access_type': 'offline',                 # OBRIGATÓRIO para obter o refresh token
        'prompt': 'consent'                       # OBRIGATÓRIO para garantir novo refresh token
    }
    
    base_url = "https://accounts.google.com/o/oauth2/auth"
    
    # Constrói a URL completa garantindo que todos os parâmetros estão codificados corretamente
    auth_url = f"{base_url}?{urlencode(params)}"
    
    print("\n--- PASSO 1: OBTENHA O CÓDIGO DE AUTORIZAÇÃO ---")
    print("1. Copie a URL abaixo:")
    print("-" * 100)
    print(auth_url)
    print("-" * 100)
    
    print("\n2. Cole a URL no seu navegador e autorize o acesso.")
    print("3. O navegador irá redirecionar para uma página 'não encontrada'.")
    print("4. Copie SOMENTE o valor do 'code=' que aparecer na URL do navegador após o redirecionamento.")
    
    # Pede o código de autorização ao usuário
    code = input("\n--- COLE O CÓDIGO DE AUTORIZAÇÃO AQUI E PRESSIONE ENTER: ")
    
    # 5. Troca o código pelo token
    if code:
        exchange_code_for_token(code.strip())

if __name__ == "__main__":
    # Habilita o transporte inseguro (HTTP) para localhost
    if os.environ.get('OAUTHLIB_INSECURE_TRANSPORT') is None:
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    main()