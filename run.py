import uvicorn
from backend.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,
    )