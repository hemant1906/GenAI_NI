from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel
from typing import Optional, Dict
from utilities.gemini_llm import GeminiLLM

llm = GeminiLLM()

class TargetPlannerState(BaseModel):
    mermaid_code: str
    target_goals: str
    extracted: Optional[str] = None
    gaps: Optional[str] = None
    roadmap: Optional[str] = None
    summary: Optional[str] = None

# Step 1: Extract Capabilities and Components
def extract_components(state):
    prompt = f"""
    Analyze this Mermaid code and extract:
    - Key business capabilities
    - System components

    Mermaid Code:
    {state.mermaid_code}
    """
    response=llm(prompt)
    return {"extracted": response}


# Step 2: Match against Target Goals
def match_gaps(state):
    prompt = f"""
    Based on this architecture:
    {state.extracted}

    And the following target goals:
    {state.target_goals}

    Identify architectural gaps and missing elements.
    """
    response = llm(prompt)
    return {"gaps": response}


# Step 3: Generate Roadmap
def generate_roadmap(state):
    prompt = f"""
    Given these gaps:
    {state.gaps}

    Create a 3-phase migration roadmap to meet the goals.
    """
    response = llm(prompt)
    return {"roadmap": response}


# Step 4: Summarize Full Plan
def summarize_all(state):
    prompt = f"""
    Summarize the complete architecture transition plan:

    Extracted:
    {state.extracted}

    Gaps:
    {state.gaps}

    Roadmap:
    {state.roadmap}
    """
    response = llm(prompt)
    return {"summary": response}


# Build LangGraph pipeline
def get_target_planner_graph():
    builder = StateGraph(TargetPlannerState)

    builder.add_node("extract_components", RunnableLambda(extract_components))
    builder.add_node("match_gaps", RunnableLambda(match_gaps))
    builder.add_node("generate_roadmap", RunnableLambda(generate_roadmap))
    builder.add_node("summarize_all", RunnableLambda(summarize_all))

    builder.set_entry_point("extract_components")
    builder.add_edge("extract_components", "match_gaps")
    builder.add_edge("match_gaps", "generate_roadmap")
    builder.add_edge("generate_roadmap", "summarize_all")

    return builder.compile()