import asyncio
from typing import Any, AsyncGenerator

from langgraph.graph import END, START, StateGraph

from app.services.nodes import (
    aggregator,
    assign_workers,
    orchestrator_node,
    research_node,
    router_node,
    summary_node,
    worker_node,
)
from app.services.schemas import BlogState


def route_after_router(state: BlogState) -> str:
    if state["router_decision"].needs_search:
        return "research_node"
    return "orchestrator_node"


graph = StateGraph(BlogState)

graph.add_node("router_node", router_node)
graph.add_node("research_node", research_node)
graph.add_node("summary_node", summary_node)
graph.add_node("orchestrator_node", orchestrator_node)
graph.add_node("worker", worker_node)
graph.add_node("aggregator", aggregator)

graph.add_edge(START, "router_node")
graph.add_conditional_edges(
    "router_node",
    route_after_router,
    {
        "research_node": "research_node",
        "orchestrator_node": "orchestrator_node",
    },
)
graph.add_edge("research_node", "summary_node")
graph.add_edge("summary_node", "orchestrator_node")
graph.add_conditional_edges("orchestrator_node", assign_workers, "worker")
graph.add_edge("worker", "aggregator")
graph.add_edge("aggregator", END)

workflow = graph.compile()


def _blog_result_from_state(state: dict[str, Any], topic: str) -> dict:
    plan = state["plan"]

    return {
        "topic": topic,
        "title": plan.title,
        "intro_summary": plan.intro_summary,
        "content": state["final_blog"],
    }


def _stream_message_for_node(node_name: str, update: dict[str, Any]) -> str:
    messages = {
        "router_node": "Analyzing topic and deciding research strategy...",
        "research_node": "Researching current information...",
        "summary_node": "Summarizing research findings...",
        "orchestrator_node": "Planning blog structure...",
        "aggregator": "Finalizing and saving blog...",
    }

    if node_name == "worker":
        sections = update.get("completed_sections") or []
        if sections:
            return "Writing section..."
        task = update.get("task")
        if task is not None:
            section_title = getattr(task, "section_title", None)
            if section_title:
                return f"Writing section: {section_title}"
        return "Writing section..."

    return messages.get(node_name, f"Completed {node_name}")


async def generate_blog(topic: str) -> dict:
    result = await asyncio.to_thread(workflow.invoke, {"topic": topic})
    return _blog_result_from_state(result, topic)


async def generate_blog_stream(topic: str, user_id: str) -> AsyncGenerator[dict, None]:
    final_state: dict[str, Any] = {}

    async for update in workflow.astream({"topic": topic}, stream_mode="updates"):
        for node_name, node_update in update.items():
            if node_update:
                final_state.update(node_update)

            yield {
                "node": node_name,
                "status": "completed",
                "message": _stream_message_for_node(node_name, node_update or {}),
            }

    yield {
        "node": "done",
        "status": "completed",
        "message": "Blog generated successfully",
        "result": _blog_result_from_state(final_state, topic),
    }
