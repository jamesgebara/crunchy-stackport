import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import STACKPORT_PORT
from backend.routes import resources, s3, stats

app = FastAPI(title="StackPort", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stats.router, prefix="/api")
app.include_router(s3.router, prefix="/api/s3")
app.include_router(resources.router, prefix="/api")

# Serve UI static files (SPA fallback)
ui_dist = os.path.join(os.path.dirname(__file__), "..", "ui", "dist")
if os.path.isdir(ui_dist):
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")


def cli():
    uvicorn.run("backend.main:app", host="0.0.0.0", port=STACKPORT_PORT, reload=False)


if __name__ == "__main__":
    cli()
