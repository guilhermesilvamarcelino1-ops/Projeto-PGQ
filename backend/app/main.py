from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, auth, chat, documents, drive, filing

app = FastAPI(title="Procede API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(drive.router)
app.include_router(drive.callback_router)
app.include_router(filing.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
