
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from app.bot.dialogue_manager.dialogue_manager import DialogueManager
from app.database import client as database_client

from app.admin.bots.routes import router as bots_router
from app.admin.entities.routes import router as entities_router
from app.admin.intents.routes import router as intents_router
from app.admin.train.routes import router as train_router
from app.bot.chat.routes import router as chat_router
from app.config import app_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # initialize dialogue_manager
    dialogue_manager = await DialogueManager.from_config()
    dialogue_manager.update_model(app_config.MODELS_DIR)
    app.state.dialogue_manager : DialogueManager = dialogue_manager
    print("dialogue manager loaded")

    yield

    database_client.close()

app = FastAPI(title="AI Chatbot Framework",lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/ready")
async def ready():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Welcome to AI Chatbot Framework API"}


app.include_router(bots_router, prefix="/admin", tags=["bots"])
app.include_router(intents_router, prefix="/admin", tags=["intents"])
app.include_router(entities_router, prefix="/admin", tags=["entities"])
app.include_router(train_router, prefix="/admin", tags=["train"])
app.include_router(chat_router, prefix="/bots", tags=["bots"])