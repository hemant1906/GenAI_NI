from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
from agents.target_planner import get_target_planner_graph
from agents.pattern_selector import get_pattern_selector_graph
import json

app = FastAPI(title="ArchPilot Agentic API")

target_graph = get_target_planner_graph()
pattern_graph = get_pattern_selector_graph()

# --- Target Planner --- #
@app.post("/agent/target-planner")
def run_target_planner(
    mermaid_code: str = Body(..., embed=True)
):
    target_goals = "Improve Modularity, Adopt Microservices, Enable CI/CD, Add Observability, Improve Security, Improve System Resilience"
    result = target_graph.invoke({
        "mermaid_code": mermaid_code,
        "target_goals": target_goals
    })
    return {"summary": result["summary"]}

# --- Target Planner Stream --- #
@app.post("/agent/target-planner/stream")
def run_target_planner_stream(
    mermaid_code: str = Body(..., embed=True)
):
    target_goals = "Improve Modularity, Adopt Microservices, Enable CI/CD, Add Observability, Improve Security, Improve System Resilience"
    def event_stream():
        for event in target_graph.stream({
            "mermaid_code": mermaid_code,
            "target_goals": target_goals
        }):
            yield f"data: {json.dumps(event)}\n\n"  # SSE format

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# --- Pattern Selector --- #
@app.post("/agent/pattern-selector")
def run_pattern_selector(
    mermaid_code: str = Body(..., embed=True)
):
    result = pattern_graph.invoke({"mermaid_code": mermaid_code})
    return {"summary": result["summary"]}

# --- Pattern Selector Stream --- #
@app.post("/agent/pattern-selector/stream")
def run_pattern_selector(
    mermaid_code: str = Body(..., embed=True)
):
    def event_stream():
        for event in pattern_graph.stream({
            "mermaid_code": mermaid_code
        }):
            yield f"data: {json.dumps(event)}\n\n"  # SSE format

    return StreamingResponse(event_stream(), media_type="text/event-stream")
