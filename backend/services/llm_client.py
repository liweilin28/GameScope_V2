"""
来源：学生 + AI
作用：封装可选 LLM 调用；没有 API Key 或调用失败时提供稳定 fallback。
"""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()

DEFAULT_LLM_BASE_URL = "https://api.deepseek.com"
DEFAULT_LLM_MODEL = "deepseek-v4-flash"


def _get_api_key() -> str:
    return os.getenv("DEEPSEEK_API_KEY", "").strip()


def _get_base_url() -> str:
    return os.getenv("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).strip().rstrip("/")


def _get_model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip()


def get_llm_status() -> dict[str, Any]:
    """返回 LLM 当前可用状态。只有配置 API Key 时才启用真实调用。"""
    api_key = _get_api_key()
    base_url = _get_base_url()
    model = _get_model()
    enabled = bool(api_key and base_url and model)
    return {
        "enabled": enabled,
        "mode": "LLM Enabled" if enabled else "Rule-based fallback",
        "model": model,
        "base_url_configured": bool(base_url),
        "api_key_configured": bool(api_key),
    }


def safe_call_llm(prompt: str, system_prompt: str | None = None) -> dict[str, Any]:
    """安全调用 OpenAI-compatible chat completions 接口，失败时返回 fallback 状态。"""
    status = get_llm_status()
    if not status["enabled"]:
        return {
            "success": False,
            "llm_used": False,
            "content": "",
            "message": "未配置 DEEPSEEK_API_KEY，已使用规则 fallback。",
        }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = requests.post(
            f"{_get_base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {_get_api_key()}",
                "Content-Type": "application/json",
            },
            json={
                "model": _get_model(),
                "messages": messages,
                "temperature": 0.2,
            },
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return {"success": True, "llm_used": True, "content": content, "message": "LLM 调用成功。"}
    except Exception as exc:
        return {
            "success": False,
            "llm_used": False,
            "content": "",
            "message": f"LLM 调用失败，已使用规则 fallback：{exc}",
        }
