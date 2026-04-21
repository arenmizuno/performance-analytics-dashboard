from fastapi import FastAPI
from routes.activities import router as activities_router
from routes.graphs import router as graphs_router

app = FastAPI(title="Performance Analytics Dashboard")

app.include_router(activities_router)
app.include_router(graphs_router)

@app.get("/")
def root():
    return {"message": "Performance Analytics Dashboard API is running"}