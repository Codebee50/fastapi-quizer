from fastapi import FastAPI
from app.quizer import routers as quizer
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()

app = FastAPI()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://beequizer.site", "http://localhost:3000", "http://localhost:5000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(quizer.router)

@app.get("/health/")
def health():
    return {"status": "ok"}