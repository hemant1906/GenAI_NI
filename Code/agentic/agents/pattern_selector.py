from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from utilities.gemini_llm import GeminiLLM
from pydantic import BaseModel
from typing import Optional, Dict

llm = GeminiLLM()

class PatternSelectorState(BaseModel):
    mermaid_code: str
    extracted_info: Optional[str] = None
    evaluation: Optional[str] = None
    pattern_recommendations: Optional[str] = None
    summary: Optional[str] = None

# Step 1: Extract structure and concerns
def extract_architecture_info(state):
    prompt = f"""
    Analyze this mermaid architecture diagram and identify:
    - Architectural style (e.g., monolith, layered, service-based)
    - Integration points and communication methods
    - Observed responsibilities

    Mermaid Code:
    {state.mermaid_code}
    """
    response = llm(prompt)
    return {"extracted_info": response}

# Step 2: Evaluate design characteristics
def evaluate_design_goals(state):
    prompt = f"""
    Based on this architecture info:
    {state.extracted_info}

    Evaluate alignment with modern architecture goals like:
    - Modularity
    - Scalability
    - Fault Isolation
    - Evolvability
    - Cloud-readiness
    - Developer velocity

    Identify strengths and weaknesses.
    """
    response = llm(prompt)
    return {"evaluation": response}

# Step 3: Recommend patterns
def recommend_patterns(state):
    prompt = f"""
    Given this architecture evaluation:
    {state.evaluation}

    Recommend 2-3 architecture patterns that best align with the design and goals. Choose from:
    - Microservices
    - Layered Architecture
    - Event-Driven
    - Serverless
    - Hexagonal (Ports & Adapters)
    - CQRS
    - Modular Monolith

    For each pattern:
    - Name
    - Why it fits
    - Risks or trade-offs
    """
    response = llm(prompt)
    return {"pattern_recommendations": response}

# Step 4: Summarize final output
def summarize_result(state):
    prompt = f"""
    Summarize pattern recommendations in architect-friendly language.

    Architecture Summary:
    {state.extracted_info}

    Evaluation:
    {state.evaluation}

    Recommended Patterns:
    {state.pattern_recommendations}
    """
    response = llm(prompt)
    return {"summary": response}

# LangGraph setup
def get_pattern_selector_graph():
    builder = StateGraph(PatternSelectorState)
    builder.add_node("extract", RunnableLambda(extract_architecture_info))
    builder.add_node("evaluate", RunnableLambda(evaluate_design_goals))
    builder.add_node("recommend", RunnableLambda(recommend_patterns))
    builder.add_node("summarize", RunnableLambda(summarize_result))

    builder.set_entry_point("extract")
    builder.add_edge("extract", "evaluate")
    builder.add_edge("evaluate", "recommend")
    builder.add_edge("recommend", "summarize")

    return builder.compile()