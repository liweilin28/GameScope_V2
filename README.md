# GameScope_V2

## 项目定位

GameScope_V2 是一个基于 Steam 数据的游戏市场智能分析与独立游戏立项辅助平台。

本项目不是开发一款游戏，而是帮助独立游戏开发者基于 Steam 历史数据进行早期立项分析。用户可以上传或使用默认 Steam CSV 数据，查看市场趋势、类型分布、标签分布、价格区间、玩家口碑，并在 Idea Lab 中输入游戏创意，获得相似竞品、机会评分、差异化建议和 Project Brief。

## 技术栈

- Python
- FastAPI
- pandas
- numpy
- HTML
- CSS
- Vanilla JavaScript
- ECharts
- optional LLM

未使用 Streamlit、React、Vue、Vite、Webpack 或 npm 构建流程。

## 课程要求对应关系

| 课程要求 | V2 对应实现 |
|---|---|
| 数据读取 | 默认 CSV 读取、用户上传 CSV、数据状态接口 |
| 数据预处理 | 字段兼容、缺失值处理、去重、类型转换、衍生字段 |
| 数据分析 | 核心指标、趋势统计、类型/标签频率、排行榜、市场筛选 |
| 数据可视化 | ECharts 折线图、柱状图、横向柱状图、散点图 |
| 交互式问答 | Data Q&A 规则识别问题并基于后端结果回答 |
| PLUS 创新 | Idea Lab：创意解析、竞品雷达、机会评分、差异化建议、Project Brief |

## 功能模块

- Home：产品首页，说明项目定位和核心能力。
- Data Pipeline：展示数据来源、上传 CSV、原始/清洗预览、缺失值、字段兼容和清洗报告。
- Market Dashboard：展示游戏总数、平均价格、好评率、发行趋势、类型和标签分布。
- Visual Explorer：提供 Indie、年份、价格、类型、标签和评论数筛选，进行交互式可视化分析。
- Data Q&A：支持 8 类规则问数，AI 或模板只解释后端计算结果。
- Idea Lab：输入游戏创意，生成结构化解析、相似竞品、机会评分、差异化建议和项目简报。

## 项目目录结构

```text
GameScope_V2/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── api/
│   └── services/
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/
├── data/
│   ├── sample/
│   └── processed/
├── docs/
├── tests/
├── requirements.txt
├── README.md
└── .env.example
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行方法

```bash
python -m uvicorn backend.main:app --reload
```

## 访问地址

```text
http://127.0.0.1:8000
```

如果端口被占用，可以使用：

```bash
python -m uvicorn backend.main:app --reload --port 8001
```

## 数据文件放置方法

默认数据路径：

```text
data/sample/sample_steam_games.csv
```

项目已提供小型示例 CSV，课堂 Demo 也可以在 Data Pipeline 页面上传自己的 CSV。

## LLM 环境变量配置

复制 `.env.example` 并配置：

```env
DEEPSEEK_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

不要在代码中写死模型名或 API Key。

## Fallback 说明

没有 LLM API Key 时，项目仍然完整运行：

- Data Q&A 使用规则模板回答。
- Idea Parser 使用关键词规则解析。
- Project Brief 使用模板生成。
- 前端显示 `Rule-based fallback`。

LLM 只用于创意解析、结果解释和报告润色，不负责机会评分计算、竞品排序，也不允许编造不存在的数据。

## 测试方法

```bash
pytest
```

如果 Windows 命令行找不到 `pytest`，使用：

```bash
python -m pytest
```

## Demo 推荐路径

1. Home：说明项目不是游戏，而是 Steam 市场分析平台。
2. Data Pipeline：展示默认数据或上传 CSV，说明字段兼容和清洗报告。
3. Market Dashboard：展示核心指标和 5 个图表。
4. Visual Explorer：修改筛选条件并刷新图表。
5. Data Q&A：提问“Indie 游戏价格主要集中在哪？”
6. Idea Lab：输入创意，展示解析、机会评分、竞品雷达、差异化建议和 Project Brief。

## 常见问题

- 找不到数据文件：把 CSV 放到 `data/sample/sample_steam_games.csv`，或直接在页面上传 CSV。
- 上传 CSV 字段不完整：系统会尽量字段兼容，缺少关键字段时会显示提示，不会直接崩溃。
- LLM 未配置：属于正常 fallback 模式，不影响 Demo。
- 端口被占用：换用 `--port 8001`。
- 依赖未安装：执行 `pip install -r requirements.txt`。
