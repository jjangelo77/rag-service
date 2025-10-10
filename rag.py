import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import OpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from fastapi.middleware.cors import CORSMiddleware
# Precisamos do 'os' para construir o caminho
from dotenv import load_dotenv 

# Importa o router de agendamento (Certifique-se de que scheduler_service/main.py existe)
from scheduler_service.main import router as scheduler_router 

# --- CORREÇÃO FINAL: FORÇAR A LEITURA DO .ENV ---
# Isso garante que o Python encontre o .env independentemente do diretório de execução.
# O os.path.dirname(__file__) garante que ele olhe no mesmo diretório de rag.py
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- VERIFICAÇÃO E INICIALIZAÇÃO DA CHAVE ---

openai_api_key = os.getenv("OPENAI_API_KEY")

if not openai_api_key:
    # Se a chave não for encontrada, o aplicativo deve falhar com um erro claro.
    print("ERRO CRÍTICO: OPENAI_API_KEY não foi encontrada nas variáveis de ambiente.")
    # Este 'raise' interromperá o processo de carregamento, mas agora forçamos o caminho.
    raise ValueError("A chave OPENAI_API_KEY é obrigatória para iniciar o serviço.")

# Definir a chave de ambiente para garantir que as bibliotecas a encontrem
os.environ["OPENAI_API_KEY"] = openai_api_key

# ----------------------------------------------------------------------
# INICIALIZAÇÃO DO APP E DOS MÓDULOS
# ----------------------------------------------------------------------

app = FastAPI()

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# INCLUI O ROUTER DE AGENDAMENTO
app.include_router(scheduler_router)

# Configuração do modelo de linguagem
llm = OpenAI(temperature=0)
embeddings = OpenAIEmbeddings()

# Define o prompt do sistema para o modelo
system_prompt = """
Você é um assistente de pesquisa para o agente Jhon, um life planner.
Sua única função é extrair informações relevantes do contexto fornecido para ajudar o agente a responder a uma pergunta de cliente.
O contexto inclui:
1. Uma "ficha_do_cliente" com detalhes do cliente.
2. Uma "ficha_do_produto" com detalhes da apólice.
3. Informações de "conhecimento" sobre os produtos.

Sua tarefa é usar as informações das fichas para entender a situação do cliente e, então, buscar e extrair os pontos mais úteis e pertinentes do "conhecimento" que possam ser usados para construir uma resposta.

Responda de forma objetiva, listando os pontos-chave. Não crie uma resposta final para o cliente. Se não encontrar informações relevantes no contexto, responda apenas "Nenhuma informação relevante encontrada para esta pesquisa."
"""

# Cria o prompt do LangChain combinando a pergunta do usuário com o contexto
prompt_template = PromptTemplate(
    input_variables=["context", "question"],
    template=system_prompt + "\n\nContexto: {context}\n\nPergunta do usuário: {question}\n\nResposta:"
)

# Rota principal para a API
@app.post("/ask")
async def ask_rag(request: Request):
    body = await request.json()
    question = body.get("question")

    if not question:
        raise HTTPException(status_code=400, detail="A pergunta não pode estar vazia.")

    # A base de conhecimento única agora é 'faiss_index', conforme sua decisão
    index_path = "faiss_index"

    try:
        # Carrega a base de conhecimento a partir do índice FAISS
        vector_store = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
        retriever = vector_store.as_retriever()

        # Cria a cadeia de recuperação de dados
        chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": prompt_template}
        )
        
        response = chain.invoke({"query": question})
        return {"message": response["result"]}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Índice FAISS não encontrado. Verifique se o arquivo '{index_path}' existe.")
    except Exception as e:
        print(f"Erro ao processar a requisição: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)