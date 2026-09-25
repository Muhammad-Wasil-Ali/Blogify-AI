from langchain.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from langgraph.constants import Send

from app.config import settings
from app.services.schemas import BlogState, EvidenceItem, EvidencePack, Plan, RouterDecision, WorkerState


llm = ChatGroq(model=settings.OPENAI_MODEL, api_key=settings.GROQ_API_KEY)
fast_llm = ChatGroq(
    model=settings.QWEN_MODEL,
    api_key=settings.GROQ_API_KEY,
    max_tokens=512,
)
orchestrator_llm = ChatGroq(model=settings.OPENAI_MODEL, api_key=settings.GROQ_API_KEY)
structured_llm = orchestrator_llm.with_structured_output(Plan)
router_llm = llm.with_structured_output(RouterDecision)
tavily_search = TavilySearchResults(
    max_results=5,
    api_wrapper=TavilySearchAPIWrapper(tavily_api_key=settings.TAVILY_API_KEY),
)


def router_node(state: BlogState):
    topic = state["topic"]
    system_prompt = SystemMessage(
        content=(
            "You are an expert research router for a blog-writing pipeline. "
            "Decide whether the topic needs current or factual web research before writing. "
            "If research is needed, generate 2-4 focused search queries."
        )
    )
    human_message = HumanMessage(
        content=(
            f"Topic: {topic}\n\n"
            "Return whether search is needed. Search is needed for current events, fast-changing topics, "
            "statistics, comparisons, tools, product details, or factual claims that should be verified. "
            "Search is not needed for evergreen conceptual or purely creative topics."
        )
    )

    decision = router_llm.invoke([system_prompt, human_message])
    if decision.needs_search and not decision.search_queries:
        decision.search_queries = [topic]
    if decision.search_queries:
        decision.search_queries = decision.search_queries[:4]
    print("Router Node done")
    return {"router_decision": decision}


def research_node(state: BlogState):
    decision = state["router_decision"]
    evidence_packs: list[EvidencePack] = []

    for query in decision.search_queries:
        search_results = tavily_search.invoke({"query": query})
        evidence_items: list[EvidenceItem] = []

        for item in search_results:
            if not isinstance(item, dict):
                continue
            evidence_items.append(
                EvidenceItem(
                    title=item.get("title") or "",
                    url=item.get("url") or "",
                    content=item.get("content") or item.get("snippet") or "",
                )
            )

        evidence_packs.append(EvidencePack(query=query, results=evidence_items))

    print("Research Node done")
    return {"evidence_packs": evidence_packs}


def summary_node(state: BlogState):
    evidence_text = []
    for pack in state.get("evidence_packs", []):
        evidence_text.append(f"Query: {pack.query}")
        for item in pack.results:
            evidence_text.append(f"- {item.title}\n  URL: {item.url}\n  Content: {item.content}")

    system_prompt = SystemMessage(
        content=(
            "You are an expert research summarizer. Condense search evidence into compact, "
            "useful bullet points for a blog planner. Keep factual claims grounded in the evidence."
        )
    )
    human_message = HumanMessage(
        content=(
            f"Topic: {state['topic']}\n\n"
            "Evidence:\n"
            f"{chr(10).join(evidence_text)}\n\n"
            "Create a compact bullet-point summary of the most useful facts, trends, examples, "
            "and source-backed angles for planning the blog. Aim for 6-8 short, dense bullet points, "
            "each under 20 words."
        )
    )

    result = fast_llm.invoke([system_prompt, human_message])
    print("Summary Node done")
    return {"evidence_summary": result.content}


def orchestrator_node(state: BlogState):
    topic = state["topic"]
    evidence_summary = state.get("evidence_summary")
    system_prompt = SystemMessage(content=f"""You are an expert blog content strategist and planner.
                Your job is to break down a blog topic into a clear, logical set of sections 
                that together form a complete, well-structured blog post.""")
    evidence_context = f"\n\nResearch summary:\n{evidence_summary}" if evidence_summary else ""
    human_message = HumanMessage(content=f"Topic: {topic}{evidence_context}\n\n"
                """Create a blog plan. 
                Each section should have a clear title, a description of what it should cover, 
                and its order in the blog. Make sure the flow goes from introduction to conclusion.
                If a research summary is provided, populate each section's relevant_facts field with facts specific to that section.""")

    plan = structured_llm.invoke([system_prompt, human_message])
    print("Orchestrting done...")
    return {"plan": plan}


def assign_workers(state: BlogState):
    """Takes the plan's tasks and dispatches one Send per task, in parallel."""
    return [
        Send("worker", {"task": t})
        for t in state["plan"].tasks
    ]


def worker_node(state: WorkerState):
    task = state["task"]

    system_prompt = SystemMessage(
        content=(
            "You are an expert blog writer. Write clear, engaging, well-structured "
            "content in Markdown format. Use proper Markdown syntax: ## for the section "
            "heading, **bold** for emphasis, - for bullet points, and short paragraphs."
        )
    )

    human_message = HumanMessage(
        content=(
            f"Write a blog section titled: {task.section_title}\n\n"
            f"Instructions: {task.description}  , Related Tags  : {task.keywords}"
            f", Relevant Facts  : {task.relevant_facts}"
            f"Return only the Markdown content for this section — no extra commentary."
        )
    )

    result = llm.invoke([system_prompt, human_message])
    print("Worker Node done")
    return {"completed_sections": [result.content]}


def aggregator(state: BlogState):
    combined_markdown = "\n\n".join(state["completed_sections"])
    final_content = f"# {state['plan'].title}\n\n{combined_markdown}"

    return {"final_blog": final_content}
