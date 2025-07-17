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
    thoughts: Optional[Dict[str, str]] = {}

# Step 1: Extract Capabilities and Components
def extract_components(state):
    prompt = f"""
    Analyze this Mermaid code and extract:
    - Key business capabilities
    - System components

    Mermaid Code:
    {state.mermaid_code}

    First, explain your reasoning and assumptions.
    Then list the components. Use markdown headers:
    ### Reasoning
    ### Extracted
    
    Limit total response to 300 words.
    """
    full_response = llm(prompt)

    reasoning, extracted = full_response, full_response
    if "### Extracted" in full_response:
        parts = full_response.split("### Extracted", 1)
        reasoning = parts[0].strip()
        extracted = "### Extracted\n" + parts[1].strip()

    return {
        "extracted": extracted,
        "thoughts": {
            "extract": reasoning
        }
    }

# Step 2: Check if architecture meets industry goals
def assess_alignment(state):
    prompt = f"""
    Evaluate the extracted components:
    {state.extracted}

    Against target goals:
    {state.target_goals}

    First reason your assessment, then score how well it meets these goals (0-100) and briefly explain only in one line for each scoring and return:
    ### Reasoning
    ### Assessment (Score and Brief explanation)
    
    Limit total response to 300 words.
    """
    full_response = llm(prompt)

    reasoning, assessment = full_response, full_response
    if "### Assessment" in full_response:
        parts = full_response.split("### Assessment", 1)
        reasoning = parts[0].strip()
        assessment = "### Assessment\n" + parts[1].strip()

    return {
        "assessment": assessment,
        "thoughts": {
            "assess": reasoning
        }
    }

# Step 2.5: Decide path based on assessment

def route_based_on_alignment(state):
    score_prompt = f"""
    Extract a score from this text (0-100). Only return a number.
    Text:
    {state.assessment}
    """
    score_text = llm(score_prompt)
    score = int(''.join(filter(str.isdigit, score_text)))
    return "enhancement" if score > 70 else "full_planning"

# Step 3a: Minor enhancement path
def suggest_enhancements(state):
    prompt = f"""
    Based on current capabilities:
    {state.extracted}

    Suggest 2–3 enhancements to better meet goals:
    {state.target_goals}

    First explain your thought process.

    Then return:
    ### Reasoning
    ### Recommendations
    
    Only include WHY. Do not include HOW TO IMPLEMENT. Overall this must not exceed 300 words. 
    """
    full_response = llm(prompt)

    reasoning, summary = full_response, full_response
    if "### Recommendations" in full_response:
        parts = full_response.split("### Recommendations", 1)
        reasoning = parts[0].strip()
        summary = "### Recommendations\n" + parts[1].strip()

    return {
        "summary": summary,
        "thoughts": {
            "enhance": reasoning
        }
    }

# Step 3b: Full roadmap generation path
def identify_gaps(state):
    prompt = f"""
    Identify architecture gaps in:
    {state.extracted}

    Compared to:
    {state.target_goals}

    Return top 3 gaps with 1–2 line suggestions.

    Use markdown:
    ### Reasoning
    ### Gaps (Top 3)
    """
    full_response = llm(prompt)

    reasoning, gaps = full_response, full_response
    if "### Gaps" in full_response:
        parts = full_response.split("### Gaps", 1)
        reasoning = parts[0].strip()
        gaps = "### Gaps\n" + parts[1].strip()

    return {
        "gaps": gaps,
        "thoughts": {
            "identify_gaps": reasoning
        }
    }


def roadmap_planning(state):
    prompt = f"""
    Create a 3-phase roadmap to address these gaps:
    {state.gaps}

    Explain your thinking first.

    Then return:
    ### Reasoning
    ### Roadmap
    
    Limit the overall response within 250 words.
    """
    full_response = llm(prompt)

    reasoning, roadmap = full_response, full_response
    if "### Roadmap" in full_response:
        parts = full_response.split("### Roadmap", 1)
        reasoning = parts[0].strip()
        roadmap = "### Roadmap\n" + parts[1].strip()

    return {
        "roadmap": roadmap,
        "thoughts": {
            "plan_roadmap": reasoning
        }
    }

def summarize_roadmap(state):
    prompt = f"""
    Summarize this architecture transition plan:
    Extracted: {state.extracted}
    Gaps: {state.gaps}
    Roadmap: {state.roadmap}

    First explain reasoning, then return:
    ### Reasoning
    ### Summary
    
    Limit the overall response to 300 words.
    """
    full_response = llm(prompt)

    reasoning, summary = full_response, full_response
    if "### Summary" in full_response:
        parts = full_response.split("### Summary", 1)
        reasoning = parts[0].strip()
        summary = "### Summary\n" + parts[1].strip()

    return {
        "summary": summary,
        "thoughts": {
            "summarize_roadmap": reasoning
        }
    }

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
