"""UC Dining Favorites. Run with: uvicorn app.main:app --reload, then open http://127.0.0.1:8000"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.database import engine
from app.ingest import init_db
from app.routers import favorites, locations, menus

PAGE = Path(__file__).parent / "static" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(engine)
    yield


app = FastAPI(
    title="UC Dining Favorites",
    description="Browse UC dining hall menus by diet, save favorite dishes, and see where and when they're served.",
    lifespan=lifespan,
)
app.include_router(locations.router)
app.include_router(menus.router)
app.include_router(favorites.router)


@app.get("/", include_in_schema=False)
def home():
    """The web page. The JSON API it uses is documented at /docs."""
    return FileResponse(PAGE)
