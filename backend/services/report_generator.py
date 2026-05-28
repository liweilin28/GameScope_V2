"""
来源：学生 + AI
作用：基于结构化分析结果生成差异化建议和 Project Brief。
"""

from __future__ import annotations

from collections import Counter

from backend.services.llm_client import safe_call_llm


def generate_differentiation_cards(idea_profile: dict, competitors: list[dict], opportunity_score: dict) -> list[dict]:
    """根据创意画像、竞品标签和机会评分生成四类差异化建议。"""
    tag_counter = Counter()
    for game in competitors:
        for tag in str(game.get("tags", "")).replace("|", ",").replace(";", ",").split(","):
            tag = tag.strip()
            if tag:
                tag_counter[tag] += 1
    crowded_tags = [tag for tag, _ in tag_counter.most_common(5)]
    user_tags = idea_profile.get("target_tags", [])

    cards = [
        {
            "title": "玩法机制差异化",
            "content": f"竞品常见标签为 {', '.join(crowded_tags) or '暂无'}。建议围绕 {', '.join(user_tags) or '核心玩法'} 做一个可在 10 分钟内感知的独特机制。",
        },
        {
            "title": "叙事主题差异化",
            "content": f"保留 {', '.join(idea_profile.get('narrative_keywords', []) or ['叙事'])}，避免只复制竞品高频主题，用更具体的角色关系或情绪目标切入。",
        },
        {
            "title": "美术风格差异化",
            "content": f"美术关键词为 {', '.join(idea_profile.get('art_style_keywords', []) or ['待明确'])}。建议用低成本但强识别度的视觉规则建立商店页第一印象。",
        },
        {
            "title": "竞品避让策略",
            "content": f"当前机会总分 {opportunity_score.get('total_score', 'N/A')}。若竞品相似度高，应优先避开同价位、同标签组合，先验证垂直人群。",
        },
    ]
    return cards


def generate_project_brief(analysis_result: dict, use_llm: bool = True) -> tuple[str, bool]:
    """基于结构化分析结果生成 Project Brief，LLM 只做可选改写。"""
    profile = analysis_result.get("idea_profile", {})
    score = analysis_result.get("opportunity_score", {})
    competitors = analysis_result.get("competitors", [])
    cards = analysis_result.get("differentiation_cards", [])

    brief = f"""## 1. 目标方向
目标类型：{', '.join(profile.get('target_genres', []))}
目标标签：{', '.join(profile.get('target_tags', []))}
价格区间：{profile.get('price_range')}

## 2. 创意解析
玩法关键词：{', '.join(profile.get('gameplay_keywords', []))}
叙事关键词：{', '.join(profile.get('narrative_keywords', []))}
美术关键词：{', '.join(profile.get('art_style_keywords', []))}

## 3. 市场机会评分
总分：{score.get('total_score')}
结论：{score.get('conclusion')}

## 4. 竞品分析
相似竞品数量：{len(competitors)}
代表竞品：{', '.join([item.get('name', 'Unknown') for item in competitors[:5]])}

## 5. 关键风险
如果竞品数量较多或相似度较高，需要避免直接进入拥挤标签组合；如果样本量不足，应先用小体量 Demo 验证。

## 6. 差异化建议
{chr(10).join([f"- {card['title']}：{card['content']}" for card in cards])}

## 7. 初步立项结论
建议将该方向作为早期验证候选，并优先测试核心机制、商店页卖点和目标玩家反馈。

## 8. 数据使用边界
该报告仅基于当前 CSV 数据和规则分析生成，不能代表完整 Steam 市场，也不替代真实商业决策。
"""
    if use_llm:
        llm = safe_call_llm(
            f"请只基于以下报告改写成更清晰的中文项目简报，不要新增数据：\n{brief}",
            "你是游戏市场分析报告编辑，只能改写给定内容。",
        )
        if llm["success"] and llm["content"]:
            return llm["content"], True
    return brief, False
