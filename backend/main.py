"""
来源：学生 + AI
作用：FastAPI 应用入口，负责注册 API 路由、系统状态接口和前端静态文件托管。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api import data_routes, dashboard_routes, explorer_routes, idea_lab_routes, qa_routes, system_routes
from backend.config import FRONTEND_DIR, get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data_routes.router)
app.include_router(system_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(explorer_routes.router)
app.include_router(qa_routes.router)
app.include_router(idea_lab_routes.router)


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    candidate = FRONTEND_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(FRONTEND_DIR / "index.html")
