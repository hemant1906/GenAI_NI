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
    thoughts: Optional[Dict[str, str]] = {}

def extract_info(state):
    prompt = f"""
    Based on the following Mermaid diagram:

    {state.mermaid_code}

    First, explain your reasoning — what do you observe about the structure and communication patterns?
    Then, clearly describe the architecture style and communication methods.

    Use Markdown. Keep the total response under 200 words.
    Label your explanation as ### Reasoning and the result as ### Observation.
    """
    full_response = llm(prompt)
    reasoning = ""
    observation = full_response

    # Make splitting work for both ** or ### headers
    if "### Observation" in full_response:
        parts = full_response.split("### Observation", 1)
        reasoning = parts[0].strip()
        observation = "### Observation\n" + parts[1].lstrip()
    elif "**Observation**" in full_response:
        parts = full_response.split("**Observation**", 1)
        reasoning = parts[0].strip()
        observation = "**Observation**\n" + parts[1].lstrip()

    return {
        "info": observation,
        "thoughts": {
            **(state.thoughts or {}),
            "extract": reasoning
        }
    }

def detect_structure_type(state):
    prompt = f"""
    Based on this:
    {state.info}

    What architecture style best describes it?
    Options: Monolith, Modular Monolith, Layered, Microservices, Event-driven
    Return only one and do not explain.
    """
    structure = llm(prompt).lower()
    if "micro" in structure: return "microservices"
    elif "event" in structure: return "event"
    elif "monolith" in structure: return "monolith"
    else: return "layered"

def microservices_path(state):
    prompt = f"""
    Based on the extracted insights below:

    {state.info}

    First, explain why microservices patterns are appropriate for this architecture.
    Then, recommend suitable patterns (e.g. API Gateway, Service Mesh, CQRS).

    Label the reasoning as ### Reasoning, and the suggestions as ### Recommendation.
    Use Markdown. Stay under 200 words.
    """
    full_response = llm(prompt)

    reasoning = ""
    recommendation = full_response

    # Make splitting work for both ** or ### headers
    if "### Recommendation" in full_response:
        parts = full_response.split("### Recommendation", 1)
        reasoning = parts[0].strip()
        recommendation = "### Recommendation\n" + parts[1].lstrip()
    elif "**Recommendation**" in full_response:
        parts = full_response.split("**Recommendation**", 1)
        reasoning = parts[0].strip()
        recommendation = "**Recommendation**\n" + parts[1].lstrip()

    return {
        "summary": recommendation,
        "thoughts": {
            "microservices": reasoning
        }
    }

def monolith_path(state):
    prompt = f"""
    Based on the extracted insights below:

    {state.info}

    First, explain your thinking about modernization strategies for monolithic systems.
    Then, suggest modernization steps (e.g. modularization, layering, service extraction).

    Label the reasoning as ### Reasoning, and the suggestions as ### Recommendation.
    Use Markdown. Keep under 200 words.
    """
    full_response = llm(prompt)

    reasoning = ""
    recommendation = full_response

    # Make splitting work for both ** or ### headers
    if "### Recommendation" in full_response:
        parts = full_response.split("### Recommendation", 1)
        reasoning = parts[0].strip()
        recommendation = "### Recommendation\n" + parts[1].lstrip()
    elif "**Recommendation**" in full_response:
        parts = full_response.split("**Recommendation**", 1)
        reasoning = parts[0].strip()
        recommendation = "**Recommendation**\n" + parts[1].lstrip()

    return {
        "summary": recommendation,
        "thoughts": {
            "monolith": reasoning
        }
    }

def layered_path(state):
    prompt = f"""
    Based on the following:

    {state.info}

    First, explain why a layered architecture is appropriate or where it can be improved.
    Then suggest refinements (e.g. isolating responsibilities, separation of concerns).

    Label the reasoning as ### Reasoning, and the suggestions as ### Recommendation.
    Use Markdown. Stay under 200 words.
    """

    full_response = llm(prompt)

    reasoning = ""
    recommendation = full_response

    # Make splitting work for both ** or ### headers
    if "### Recommendation" in full_response:
        parts = full_response.split("### Recommendation", 1)
        reasoning = parts[0].strip()
        recommendation = "### Recommendation\n" + parts[1].lstrip()
    elif "**Recommendation**" in full_response:
        parts = full_response.split("**Recommendation**", 1)
        reasoning = parts[0].strip()
        recommendation = "**Recommendation**\n" + parts[1].lstrip()

    return {
        "summary": recommendation,
        "thoughts": {
            "layered": reasoning
        }
    }

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
