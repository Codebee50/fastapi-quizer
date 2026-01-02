from fastapi import FastAPI
from app import config
from app.quizer import routers as quizer
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from app.monitor import start_monitoring
from app.documents import routers as documents


load_dotenv()

app = FastAPI(
    title="Document Processing Microservice",
    description="API for Document Processing Microservice for Studybear",
    version=config.VERSION,
    contact={
        "name": "Beequizer",
        "url": "https://beequizer.site",
        "email": "onuhudoudo@gmail.com",
    },
)


# instrumentator = Instrumentator()
# instrumentator.instrument(app).expose(app)


@app.on_event("startup")
async def startup_event():
    if config.ENVIRONMENT == 'development':
        start_monitoring()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://beequizer.site", "http://localhost:3000", "http://localhost:8080"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(quizer.router, prefix="/quiz", tags=["Quiz"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])

@app.get("/health/")
def health():
    return {
        "status": "ok",
        "version": config.VERSION
    }