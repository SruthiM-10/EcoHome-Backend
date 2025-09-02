# app/main.py
from fastapi import FastAPI
from app.db.database import engine
from app.db.models import Base  # Import your models
from app.auth import routes as auth_routes

app = FastAPI()

# This line creates all tables (only run once)
Base.metadata.create_all(bind=engine)

# app.include_router(auth_routes.router, prefix="/auth", tags=["Auth"])
app.include_router(auth_routes.router)