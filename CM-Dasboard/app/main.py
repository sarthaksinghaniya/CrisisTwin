from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import auth, crises

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

@app.get("/")
def root():
    return {"message": "Welcome to Crisis Twin AI API"}

app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["login"])
app.include_router(crises.router, prefix=f"{settings.API_V1_STR}/crises", tags=["crises"])
