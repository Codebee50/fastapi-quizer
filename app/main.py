from fastapi import FastAPI
from app.quizer import routers as quizer
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()


app.include_router(quizer.router)

@app.get("/health/")
def health():
    return {"status": "ok"}