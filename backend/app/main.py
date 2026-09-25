from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.blogs import router as blogs_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://blogify-three-rouge.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(blogs_router)