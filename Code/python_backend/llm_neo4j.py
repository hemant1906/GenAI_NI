from fastapi import FastAPI
# from langchain.graphs import Neo4jGraph
from langchain.chains import GraphCypherQAChain
# from langchain.llms import LlamaCpp
from pydantic import BaseModel
from langchain_community.graphs import Neo4jGraph
from langchain_community.llms import LlamaCpp

app = FastAPI()

# 1. Setup Neo4j
graph = Neo4jGraph(
    url="bolt://localhost:7687",
    username="neo4j",
    password="password123"
)

# 2. Lightweight model with LlamaCpp
llm = LlamaCpp(
    model_path=r"C:\Users\sourav\Downloads\GenAI\gguf\phi3:3.8b.gguf",  # adjust this path
    n_ctx=2048,
    temperature=0.2,
    top_p=0.95,
    max_tokens=512,
    verbose=True
)

# 3. Setup LangChain
chain = GraphCypherQAChain.from_llm(llm=llm, graph=graph, verbose=True)

# 4. Request body
class Query(BaseModel):
    question: str

@app.post("/ask")
async def ask_graph(query: Query):
    try:
        result = chain.run(query.question)
        return {"question": query.question, "response": result}
    except Exception as e:
        return {"error": str(e)}
