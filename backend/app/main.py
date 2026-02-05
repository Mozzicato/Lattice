from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from .database import engine, Base
from .api.v1 import documents, sessions
from .api.v1 import jobs

app = FastAPI(title="Lattice API", description="Backend for Lattice - The Thinking Companion")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Runtime checks (non-fatal warnings only)
    import logging
    log = logging.getLogger(__name__)

    # Vision LLM pipeline is active. Legacy OCR checks removed.
    log.info("Lattice Backend started with Vision LLM pipeline.")

@app.get("/health")
async def health_check():
    """Return simple health and dependency diagnostics."""
    return {
        "status": "healthy",
        "pipeline": "vision-llm"
    }

# Serve Frontend
# Build path relative to this file: ../../../frontend/build
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "build")

if os.path.exists(frontend_path):
    print(f"Serving frontend from {frontend_path}")
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"Frontend build not found at {frontend_path}")
    @app.get("/")
    async def root():
        return {"message": "Lattice API is running. Frontend build not found."}
