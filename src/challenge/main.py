import sys
from pathlib import Path
from fastapi import FastAPI

# Ensure service root is in sys.path when executing directly
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.routers.catalog import router as catalog_router

app = FastAPI(
    title="Conecta Nexus - Challenge Service",
    description="Challenge Management Microservice for Conecta Nexus",
    version="0.1.0",
)

# Mount catalog router under API v1 prefix and root alias for flexible routing
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(catalog_router)


@app.get("/")
def read_root():
    return {
        "service": "challenge",
        "status": "running",
        "framework": "fastapi",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.challenge.main:app", host="0.0.0.0", port=8000, reload=True)
