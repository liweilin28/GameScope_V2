"""
来源：学生 + AI
作用：集中管理项目路径、环境变量和阶段 1 基础配置。
"""

from functools import lru_cache
from pathlib import Path
import os

from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
SAMPLE_DATA_PATH = DATA_DIR / "sample" / "sample_steam_games.csv"
PROCESSED_DATA_PATH = DATA_DIR / "processed" / "steam_games_cleaned.csv"


class Settings(BaseModel):
    app_name: str = "GameScope_V2"
    app_version: str = "0.1.0"
    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY")
    llm_base_url: str | None = os.getenv("LLM_BASE_URL")
    llm_model: str | None = os.getenv("LLM_MODEL")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.deepseek_api_key and self.llm_base_url and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
