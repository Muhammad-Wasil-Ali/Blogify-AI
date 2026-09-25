import json
import io
import logging
import re
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
import markdown2
from xhtml2pdf import pisa

from app.auth import get_current_user_id
from app.db import supabase
from app.schemas import BlogResponse, GenerateBlogRequest
from app.services.graph import generate_blog, generate_blog_stream


router = APIRouter(tags=["blogs"])
logger = logging.getLogger(__name__)


def save_generated_blog(generated_blog: dict, user_id: str) -> dict:
    insert_payload = {
        "user_id": user_id,
        "topic": generated_blog["topic"],
        "title": generated_blog["title"],
        "intro_summary": generated_blog["intro_summary"],
        "content": generated_blog["content"],
    }

    response = supabase.table("blogs").insert(insert_payload).execute()
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blog was generated but could not be saved.",
        )

    return response.data[0]


def sse_event(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "blog"


def get_owned_blog_for_download(blog_id: str, user_id: str) -> dict:
    response = (
        supabase.table("blogs")
        .select("title, intro_summary, content")
        .eq("id", blog_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")

    return response.data[0]


def build_markdown_download_content(blog: dict) -> str:
    return f"# {blog['title']}\n\n{blog['intro_summary']}\n\n{blog['content']}"


def build_pdf_html(markdown_content: str) -> str:
    body_html = markdown2.markdown(markdown_content)
    return f"""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page {{
            margin: 1in;
        }}
        body {{
            color: #1f2937;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
        }}
        h1 {{
            color: #111827;
            font-size: 26pt;
            line-height: 1.2;
            margin: 0 0 18pt;
        }}
        h2 {{
            color: #111827;
            font-size: 17pt;
            margin: 24pt 0 8pt;
        }}
        h3 {{
            color: #111827;
            font-size: 13pt;
            margin: 18pt 0 6pt;
        }}
        p {{
            margin: 0 0 10pt;
        }}
        ul, ol {{
            margin: 0 0 10pt 20pt;
            padding: 0;
        }}
        code {{
            background: #f3f4f6;
            border-radius: 3px;
            padding: 1pt 3pt;
        }}
        blockquote {{
            border-left: 3pt solid #d1d5db;
            color: #4b5563;
            margin: 12pt 0;
            padding-left: 12pt;
        }}
    </style>
</head>
<body>
{body_html}
</body>
</html>
"""


@router.post("/generate-blog", response_model=BlogResponse)
async def create_blog(
    request: GenerateBlogRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        generated_blog = await generate_blog(request.topic)
    except Exception as exc:
        logger.exception("Blog generation failed for topic %r", request.topic)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blog generation failed. Please try again.",
        ) from exc

    return save_generated_blog(generated_blog, user_id)


@router.post("/generate-blog/stream")
async def create_blog_stream(
    request: GenerateBlogRequest,
    user_id: str = Depends(get_current_user_id),
):
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in generate_blog_stream(request.topic, user_id):
                if event.get("node") == "done":
                    saved_blog = save_generated_blog(event["result"], user_id)
                    event["result"] = saved_blog

                yield sse_event(event)
        except Exception as exc:
            yield sse_event(
                {
                    "node": "error",
                    "status": "failed",
                    "message": str(exc) or "Blog generation failed. Please try again.",
                }
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/blogs", response_model=list[BlogResponse])
async def list_blogs(user_id: str = Depends(get_current_user_id)):
    response = (
        supabase.table("blogs")
        .select("id, topic, title, intro_summary, content, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    return response.data or []


@router.get("/blogs/{blog_id}", response_model=BlogResponse)
async def get_blog(blog_id: str, user_id: str = Depends(get_current_user_id)):
    response = (
        supabase.table("blogs")
        .select("id, topic, title, intro_summary, content, created_at")
        .eq("id", blog_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")

    return response.data[0]


@router.get("/blogs/{blog_id}/download/markdown")
async def download_blog_markdown(blog_id: str, user_id: str = Depends(get_current_user_id)):
    blog = get_owned_blog_for_download(blog_id, user_id)
    markdown_content = build_markdown_download_content(blog)
    filename = f"{slugify(blog['title'])}.md"

    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/blogs/{blog_id}/download/pdf")
async def download_blog_pdf(blog_id: str, user_id: str = Depends(get_current_user_id)):
    blog = get_owned_blog_for_download(blog_id, user_id)
    markdown_content = build_markdown_download_content(blog)
    html_content = build_pdf_html(markdown_content)
    pdf_buffer = io.BytesIO()
    pisa.CreatePDF(html_content, dest=pdf_buffer)
    pdf_content = pdf_buffer.getvalue()
    filename = f"{slugify(blog['title'])}.pdf"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/blogs/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blog(blog_id: str, user_id: str = Depends(get_current_user_id)):
    existing = (
        supabase.table("blogs")
        .select("id")
        .eq("id", blog_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")

    supabase.table("blogs").delete().eq("id", blog_id).eq("user_id", user_id).execute()
    return None
