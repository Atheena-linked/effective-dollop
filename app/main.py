from fastapi import FastAPI
from app.routes import medication_routes, conflict_routes, timeline_routes,  analytics


app = FastAPI()

@app.get("/")
def root():
    return {"message":"API is running"}

app.include_router(medication_routes.router)
app.include_router(conflict_routes.router)
app.include_router(timeline_routes.router)
app.include_router(analytics.router)