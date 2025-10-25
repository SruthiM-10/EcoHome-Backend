# app/main.py
from fastapi import FastAPI
from app.db.database import engine
from app.db.models import Base  # Import your models
from app.auth import routes as auth_routes
from app.api import routes as api_routes
from app.llm import routes as llm_routes

app = FastAPI()

# This line creates all tables (only run once)
Base.metadata.create_all(bind=engine)

app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(api_routes.router, prefix="/api", tags=["api"])
app.include_router(llm_routes.router, prefix="/llm", tags=["llm"])
# app.include_router(auth_routes.router)