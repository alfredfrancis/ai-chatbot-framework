
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, APIRouter
from app.database import client as database_client
from app.dependencies import init_dialogue_manager

from app.admin.bots.routes import router as bots_router
from app.admin.entities.routes import router as entities_router
from app.admin.intents.routes import router as intents_router
from app.admin.train.routes import router as train_router
from app.bot.chat.routes import router as chat_router


@asynccontextmanager
async def lifespan(_):
    await init_dialogue_manager()
    yield 
    database_client.close()

app = FastAPI(title="AI Chatbot Framework",lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/ready")
async def ready():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Welcome to AI Chatbot Framework API"}

# admin apis
admin_router = APIRouter(prefix="/admin", tags=["admin"])
admin_router.include_router(bots_router)
admin_router.include_router(intents_router)
admin_router.include_router(entities_router)
admin_router.include_router(train_router)
app.include_router(admin_router)

app.include_router(chat_router, prefix="/bots", tags=["bots"])