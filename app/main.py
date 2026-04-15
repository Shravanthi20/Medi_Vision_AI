from fastapi import FastAPI
from app.auth.routes import router as auth_router
from app.database import engine
from app.models import Base
import asyncio

app = FastAPI(title="Selvam Medicals — Smart AI Pharma ERP System")

app.include_router(auth_router)

@app.on_event("startup")
async def startup():
    # Automatically create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {"message": "Selvam Medicals AI Pharma ERP - Authentication Module"}
