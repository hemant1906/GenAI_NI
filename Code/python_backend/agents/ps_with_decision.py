from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from utilities.gemini_llm import GeminiLLM
from pydantic import BaseModel
from typing import Optional, Dict

llm = GeminiLLM()

class PatternSelectorState(BaseModel):
    mermaid_code: str
    info: Optional[str] = None
    # evaluation: Optional[str] = None
    # pattern_recommendations: Optional[str] = None
    summary: Optional[str] = None

def extract_info(state):
    prompt = f"""
    Describe the architecture style and communication methods based on:
    {state.mermaid_code}
    
    Response should not exceed 200 words.
    """
    response = llm(prompt)
    return {"info": response}

def detect_structure_type(state):
    prompt = f"""
    Based on this:
    {state.info}

    What architecture style best describes it?
    Options: Monolith, Modular Monolith, Layered, Microservices, Event-driven
    Return only one.
    """
    structure = llm(prompt).lower()
    if "micro" in structure: return "microservices"
    elif "event" in structure: return "event"
    elif "monolith" in structure: return "monolith"
    else: return "layered"

def microservices_path(state):
    prompt = f"""
    Recommend microservices patterns (e.g. service mesh, API gateway, CQRS) for this:
    {state.info}
    
    Response should not exceed 200 words.
    """
    response = llm(prompt)
    return {"summary": response}

def monolith_path(state):
    prompt = f"""
    Recommend modernization paths (e.g. modularization, layering, extraction strategies):
    {state.info}
    
    Response should not exceed 200 words.
    """
    response = llm(prompt)
    return {"summary": response}

def layered_path(state):
    prompt = f"""
    Recommend layered architecture refinements:
    {state.info}
    
    Response should not exceed 200 words.
    """
    response = llm(prompt)
    return {"summary": response}

def get_pattern_selector_graph():
    builder = StateGraph(PatternSelectorState)
    builder.add_node("extract", RunnableLambda(extract_info))
    builder.add_node("microservices", RunnableLambda(microservices_path))
    builder.add_node("monolith", RunnableLambda(monolith_path))
    builder.add_node("layered", RunnableLambda(layered_path))

    builder.set_entry_point("extract")
    builder.add_conditional_edges("extract", detect_structure_type, {
        "microservices": "microservices",
        "event": "microservices",
        "monolith": "monolith",
        "layered": "layered"
    })

    return builder.compile()
