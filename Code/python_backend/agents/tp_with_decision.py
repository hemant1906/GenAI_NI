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
    assessment: Optional[str] = None
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
    
    Only list the components with brief one liner description for each. Overall it should not exceed 250 words.
    """
    response=llm(prompt)
    return {"extracted": response}

# Step 2: Check if architecture meets industry goals
def assess_alignment(state):
    prompt = f"""
    Analyze the extracted components:
    {state.extracted}

    Against target architecture goals:
    {state.target_goals}

    Score how well it meets these goals (0-100) and briefly explain only in one line for each scoring.
    """
    response = llm(prompt)
    return {"assessment": response}

# Step 2.5: Decide path based on assessment

def route_based_on_alignment(state):
    score_prompt = f"""
    Extract a score from this text (0-100). Only return a number.
    Text:
    {state.assessment}
    """
    score_text = llm(score_prompt)
    score = int(''.join(filter(str.isdigit, score_text)))
    return "enhancement" if score > 75 else "full_planning"

# Step 3a: Minor enhancement path
def suggest_enhancements(state):
    prompt = f"""
    Based on current state:
    {state.extracted}

    Suggest 2-3 enhancements to better meet target goals:
    {state.target_goals}
    
    Only include WHY. Do not include HOW TO IMPLEMENT. Overall this must not exceed 300 words. 
    """
    response = llm(prompt)
    return {"summary": response}

# Step 3b: Full roadmap generation path
def identify_gaps(state):
    prompt = f"""
    Identify architecture gaps from this:
    {state.extracted}

    Compared to target goals:
    {state.target_goals}
    
    Only list the gaps and recommendation with maximum 1-2 lines of description.
    """
    response = llm(prompt)
    return {"gaps": response}

def roadmap_planning(state):
    prompt = f"""
    Use these gaps:
    {state.gaps}

    Create a brief 3-phase roadmap to move toward target goals. Do not exceed 250 words.
    """
    response = llm(prompt)
    return {"roadmap": response}

def summarize_roadmap(state):
    prompt = f"""
    Summarize transition plan:
    Extracted: {state.extracted}
    Gaps: {state.gaps}
    Roadmap: {state.roadmap}
    
    Summary should not exceed 300 words.
    """
    response = llm(prompt)
    return {"summary": response}

# Build graph
def get_target_planner_graph():
    builder = StateGraph(TargetPlannerState)
    builder.add_node("extract", RunnableLambda(extract_components))
    builder.add_node("assess", RunnableLambda(assess_alignment))
    builder.add_node("enhance", RunnableLambda(suggest_enhancements))
    builder.add_node("identify_gaps", RunnableLambda(identify_gaps))
    builder.add_node("plan_roadmap", RunnableLambda(roadmap_planning))
    builder.add_node("summarize_roadmap", RunnableLambda(summarize_roadmap))

    builder.set_entry_point("extract")
    builder.add_edge("extract", "assess")
    builder.add_conditional_edges("assess", route_based_on_alignment, {
        "enhancement": "enhance",
        "full_planning": "identify_gaps"
    })
    builder.add_edge("identify_gaps", "plan_roadmap")
    builder.add_edge("plan_roadmap", "summarize_roadmap")

    return builder.compile()
