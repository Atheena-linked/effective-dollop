from fastapi import FastAPI
from app.routes import medication_routes

app = FastAPI()

@app.get("/")
def root():
    return {"message":"API is running"}

app.include_router(medication_routes.router)
