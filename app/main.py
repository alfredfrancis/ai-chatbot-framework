from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
import spacy
from config import config
import os

app = FastAPI(title="AI Chatbot Framework")

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

# Global variables
mongodb_client = None
spacy_tokenizer = None

@app.on_event("startup")
async def startup_db_client():
    global mongodb_client, spacy_tokenizer
    try:
        env = os.environ.get('APPLICATION_ENV', 'Development')
        app_config = config[env]
        
        # Store config in app state
        app.state.config = {
            "MODELS_DIR": app_config.MODELS_DIR,
            "DEFAULT_FALLBACK_INTENT_NAME": app_config.DEFAULT_FALLBACK_INTENT_NAME,
            "MONGODB_HOST": app_config.MONGODB_HOST,
            "SPACY_LANG_MODEL": app_config.SPACY_LANG_MODEL
        }
        
        # Initialize MongoDB connection
        mongodb_client = AsyncIOMotorClient(app.state.config["MONGODB_HOST"])
        app.state.mongodb = mongodb_client
        
        # Initialize Spacy
        spacy_tokenizer = spacy.load(app.state.config["SPACY_LANG_MODEL"])
        app.state.spacy_tokenizer = spacy_tokenizer
        
    except Exception as e:
        print(f"Error initializing services: {str(e)}")
        raise e

@app.on_event("shutdown")
async def shutdown_db_client():
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()

@app.get("/ready")
async def ready():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Welcome to AI Chatbot Framework API"}

# Import and include routers
from app.agents.routes import router as agents_router
from app.intents.routes import router as intents_router
from app.nlu.routes import router as nlu_router
from app.train.routes import router as train_router
from app.chat.routes import router as chat_router
from app.entities.routes import router as entities_router

# Include routers without additional prefix to maintain original URLs
app.include_router(agents_router)  # Already has /agents prefix
app.include_router(intents_router, prefix="/intents", tags=["intents"])
app.include_router(nlu_router, prefix="/nlu", tags=["nlu"])
app.include_router(train_router, prefix="/train", tags=["train"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(entities_router, prefix="/entities", tags=["entities"]) 