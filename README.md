# Blogify AI

An AI-powered blog writing agent that researches, plans, and writes complete blog posts from a single topic — using a multi-agent orchestration pipeline built with LangGraph.

**Live demo:** https://blogify-three-rouge.vercel.app

---

## What it does

Give it a topic, and Blogify AI:

1. **Routes** the topic — decides whether it needs current/real-world information or can rely on the model's own knowledge
2. **Researches** the web (when needed) using Tavily, running multiple search queries in parallel
3. **Summarizes** the research into a dense, compact set of facts
4. **Plans** a 5-section blog structure, distributing relevant facts to each section
5. **Writes** all 5 sections in parallel using a fan-out/fan-in multi-agent pattern
6. **Assembles** the final blog and saves it, ready to read, download as Markdown/PDF, or revisit later

The entire generation process streams live progress to the UI, so you can watch each step complete in real time.

---

## Architecture

### Backend pipeline (LangGraph)

```
topic
  │
  ▼
router_node ──────► decides if search is needed, generates search queries
  │
  ├── (needs search) ──► research_node ──► summary_node
  │                         (Tavily search)   (condenses evidence)
  │                                              │
  └──────────────────────────────────────────────▼
                                            orchestrator
                                    (builds a 5-section plan,
                                     assigns facts per section)
                                              │
                                              ▼
                                     assign_workers (fan-out)
                                              │
                    ┌──────────┬──────────┬──────────┬──────────┐
                    ▼          ▼          ▼          ▼          ▼
                 worker     worker     worker     worker     worker
              (section 1)(section 2)(section 3)(section 4)(section 5)
                    │          │          │          │          │
                    └──────────┴──────────┴──────────┴──────────┘
                                              │
                                              ▼
                                         aggregator
                                (merges sections, saves blog)
```

Each node's output is merged back into a shared graph state using LangGraph's reducer pattern, allowing the 5 worker nodes to write their sections concurrently without overwriting each other.

### Full stack

```
┌─────────────────────┐         ┌──────────────────────┐
│   Next.js Frontend   │  HTTPS  │   FastAPI Backend     │
│   (Vercel)           │◄───────►│   (Railway)            │
│                       │  JWT    │                        │
│  - Landing page       │  Bearer │  - Auth verification   │
│  - Auth (Google +     │  token  │  - LangGraph pipeline  │
│    email/password)    │         │  - REST + SSE streaming│
│  - Dashboard           │         │  - PDF/Markdown export │
│  - History             │         │                        │
│  - Blog viewer         │         │                        │
└──────────┬────────────┘         └───────────┬────────────┘
           │                                    │
           │         ┌──────────────┐           │
           └────────►│   Supabase   │◄──────────┘
                      │              │
                      │ - Auth (OAuth│
                      │   + email)   │
                      │ - Postgres   │
                      │   (blogs     │
                      │   table)     │
                      │ - RLS        │
                      └──────────────┘
```

---

## Tech stack

**AI / Backend**

- Python, FastAPI
- LangGraph — multi-agent orchestration (router, parallel fan-out/fan-in, conditional edges)
- LangChain + Groq — LLM inference (openai/gpt-oss-120b, qwen models)
- Tavily — real-time web search
- Pydantic — structured LLM output validation

**Auth & Data**

- Supabase Auth — Google OAuth + email/password
- Supabase Postgres — blog storage with Row Level Security
- JWT verification (HS256) on every protected API route

**Frontend**

- Next.js (App Router), TypeScript
- Tailwind CSS
- @supabase/ssr — session management across server/client components
- react-markdown — blog content rendering
- Server-Sent Events (SSE) — live generation progress

**Deployment**

- Frontend: Vercel
- Backend: Railway

---

## Key features

- **Multi-agent research & writing pipeline** — not a single LLM call, but a coordinated system of specialized agents (router, researcher, summarizer, planner, writers, aggregator)
- **Parallel section generation** — all 5 blog sections are written concurrently, not sequentially
- **Live generation progress** — real-time streaming updates as each pipeline stage completes
- **Evidence-grounded writing** — when a topic needs current facts, research is distributed to the specific sections that need it, not dumped indiscriminately
- **Full auth system** — Google OAuth and email/password, backed by Supabase
- **Blog history & management** — view, revisit, and delete past generations
- **Export** — download any generated blog as Markdown or PDF

---

## Project structure

```
blog-writing-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS config
│   │   ├── auth.py              # JWT verification dependency
│   │   ├── config.py            # Environment settings
│   │   ├── db.py                # Supabase client
│   │   ├── schemas.py           # API request/response models
│   │   ├── routers/
│   │   │   └── blogs.py         # REST + streaming endpoints
│   │   └── services/
│   │       ├── schemas.py       # LangGraph state schemas (Task, Plan, etc.)
│   │       ├── nodes.py         # Pipeline node functions
│   │       └── graph.py         # LangGraph construction
│   ├── requirements.txt
│   └── blog_agent.ipynb         # Original pipeline prototype
│
└── frontend/
    ├── app/
    │   ├── page.tsx              # Landing page
    │   ├── login/ signup/        # Auth pages
    │   ├── auth/callback/        # OAuth callback handler
    │   └── dashboard/
    │       ├── page.tsx          # Generation workspace
    │       ├── history/          # Past blogs
    │       └── blogs/[id]/       # Full blog viewer
    ├── components/
    │   ├── Sidebar.tsx
    │   └── ui/
    └── lib/
        ├── supabase/             # Client/server Supabase setup
        └── api.ts                # Backend API wrapper
```

---

## API endpoints

| Method | Endpoint                        | Description                            |
| ------ | ------------------------------- | -------------------------------------- |
| POST   | `/generate-blog`                | Generate a blog (synchronous)          |
| POST   | `/generate-blog/stream`         | Generate a blog with live SSE progress |
| GET    | `/blogs`                        | List the authenticated user's blogs    |
| GET    | `/blogs/{id}`                   | Get one blog                           |
| DELETE | `/blogs/{id}`                   | Delete a blog                          |
| GET    | `/blogs/{id}/download/markdown` | Download as `.md`                      |
| GET    | `/blogs/{id}/download/pdf`      | Download as `.pdf`                     |

All endpoints (except health checks) require a Supabase-issued JWT in the `Authorization: Bearer <token>` header.

---

## Running locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create `backend/.env`:

```env
GROQ_API_KEY=
TAVILY_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=
OPENAI_MODEL=openai/gpt-oss-120b
QWEN_MODEL=qwen/qwen3-32b
```

```bash
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm run dev
```

### Supabase setup

1. Create a project at [supabase.com](https://supabase.com)
2. Enable Google OAuth and Email/Password under **Authentication → Providers**
3. Run the following SQL in the SQL Editor:

```sql
create table blogs (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  topic text not null,
  title text,
  intro_summary text,
  content text not null,
  created_at timestamp with time zone default now()
);

alter table blogs enable row level security;

create policy "Users can view own blogs"
  on blogs for select using (auth.uid() = user_id);

create policy "Users can insert own blogs"
  on blogs for insert with check (auth.uid() = user_id);

create policy "Users can delete own blogs"
  on blogs for delete using (auth.uid() = user_id);
```

---

## Deployment

- **Frontend** is deployed on Vercel, root directory set to `frontend/`
- **Backend** is deployed on Railway, root directory set to `backend/`, started with:
  ```
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
- CORS on the backend is configured to allow the deployed frontend origin
- Google Cloud Console and Supabase redirect URLs are configured for the production domain alongside `localhost` for local development

---

## What this project demonstrates

- Designing and debugging a non-trivial multi-agent LLM pipeline (conditional branching, parallel fan-out/fan-in, shared state reducers)
- Grounding LLM output in real-time retrieved evidence, with per-section fact distribution rather than naive context stuffing
- Handling real-world constraints of working with LLM APIs — token limits, rate limits, structured output validation, schema design for reliable tool calling
- Full-stack integration: FastAPI backend, Supabase auth/data layer, Next.js frontend, JWT-based auth across services
- Streaming architecture (SSE) for real-time UX during long-running AI generation
- End-to-end deployment across two platforms with proper environment separation and CORS configuration

---

## License

MIT
