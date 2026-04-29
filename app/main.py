from fastapi import FastAPI
from app.database import engine

app = FastAPI(title="PoC Migraciones CI/CD")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "App corriendo"}
