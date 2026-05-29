# GameScope_V2

## 项目简介

GameScope_V2 是一个基于 Steam 历史数据的游戏市场智能分析与独立游戏立项辅助平台。

本项目不是开发一款游戏，而是帮助独立游戏开发者基于历史样本完成数据读取、数据预处理、数据分析、数据可视化、交互式问答和 PLUS 创新展示。系统支持默认样例数据和自定义上传数据，前端使用 HTML/CSS/Vanilla JS + ECharts，后端使用 FastAPI + pandas，适合作为课程作业验收与课堂演示项目。

## 技术栈

- Python
- FastAPI
- pandas
- numpy
- HTML
- CSS
- Vanilla JavaScript
- ECharts
- 可选 LLM 接口

未使用 React、Vue、Streamlit、Vite、Webpack 或 npm 构建流程。

## 默认样例数据规模

- 默认样例文件：`data/sample/sample_steam_games.csv`
- 实际规模：`10000` 行、`37` 列
- 课程要求：不少于 `1000` 行数据
- 当前状态：已满足课程数据规模要求

说明：项目中的默认数据可直接用于课堂演示。若需说明原始 Steam 数据外部来源，当前仓库内未附完整来源证明，提交时请学生在答辩材料中补充“数据来源待学生补充确认”。

## 功能模块

- Home：首页与课程验收面板
- Data Pipeline：数据读取、上传、预处理、字段兼容、清洗报告
- Market Dashboard：核心指标、图表和动态数据发现
- Visual Explorer：筛选与交互式可视化分析
- Data Q&A：基于真实后端计算结果的智能问数
- Idea Lab：PLUS 创新功能，提供创意解析、竞品雷达、机会评分、差异化建议和 Project Brief

## 课程要求验收表

| 验收项目 | 当前完成情况 | 对应文件或页面 | 验证方式 |
|---|---|---|---|
| 数据文件读取 | 已完成 | Data Pipeline，`backend/services/data_loader.py` | 启动后查看默认数据，或上传 CSV/TSV/XLSX/JSON |
| 数据预处理 | 已完成 | Data Pipeline，`backend/services/data_cleaner.py` | 查看清洗报告、缺失值报告、字段兼容性 |
| 数据分析方法 | 已完成 | Dashboard、Explorer、`backend/services/analyzer.py` | 查看指标、趋势、分布、筛选结果 |
| 数据可视化 | 已完成 | Dashboard、Explorer、`frontend/js/charts.js` | 查看 ECharts 折线图、柱状图、散点图 |
| 交互式分析 / 基础问答 | 已完成 | Data Q&A，`backend/api/qa_routes.py` | 输入自然语言问题，查看结构化回答 |
| PLUS 创新功能 | 已完成 | Idea Lab | 输入创意，查看竞品、评分、建议与简报 |
| AI 使用说明 | 已完成 | `docs/AI使用说明书.md` | 检查关键案例、采纳与未采纳说明 |
| 测试数据规模 | 已完成 | `data/sample/sample_steam_games.csv` | 样例数据 10000 行、37 列 |
| 测试命令 | 已完成 | `tests/` | 运行 `python3 -m pytest -q` |
| Demo 路径 | 已完成 | `docs/Demo演示脚本.md` | 按脚本进行课堂演示 |

## 运行环境与安装

推荐 Python 3.10 及以上。

macOS / Linux：

```bash
python3 -m pip install -r requirements.txt
```

Windows：

```bash
python -m pip install -r requirements.txt
```

## 启动方式

macOS / Linux：

```bash
python3 -m uvicorn backend.main:app --reload
```

Windows：

```bash
python -m uvicorn backend.main:app --reload
```

默认访问地址：

```text
http://127.0.0.1:8000
```

如果端口被占用，可改为：

macOS / Linux：

```bash
python3 -m uvicorn backend.main:app --reload --port 8001
```

Windows：

```bash
python -m uvicorn backend.main:app --reload --port 8001
```

## 数据与兼容性说明

- 默认数据路径：`data/sample/sample_steam_games.csv`
- 系统支持上传 `CSV`、`TSV`、`XLSX`、`JSON`
- 若上传数据缺少 `name` 字段，系统会尝试使用其他字符串列或 `id` 列生成 `display_name/name`
- 若上传的是非 Steam 通用表格，系统不会崩溃，但部分 Steam 专用分析会提示能力受限

## LLM 使用边界

LLM 仅用于：

- 创意解析
- 自然语言解释
- 报告润色

LLM 不用于：

- 真实统计计算
- 机会评分公式计算
- 竞品排序
- 编造不存在的数据结论

未配置 API Key 时，系统自动进入规则 fallback 模式，仍可完成课程演示。

## 一键自检

macOS / Linux：

```bash
python3 -m pytest -q
```

Windows：

```bash
python -m pytest -q
```

运行后应看到测试通过信息，表示后端接口、数据清洗、分析逻辑和 PLUS 模块处于可验收状态。

## 提交材料清单

项目已提供并强化以下材料：

- 代码仓库
- 1000+ 行测试数据
- 数据处理脚本
- README
- Demo 演示脚本
- AI 使用说明书
- 测试记录
- 数据字典
- 提交验收清单
- 代码来源标注

以下内容请学生在最终提交前补齐或确认：

- PPT 文件
- 演示视频 / demo 视频文件
- 外部数据来源最终确认说明
- 反思总结终稿

## Demo 推荐路径

1. Home：展示项目定位与课程验收面板
2. Data Pipeline：展示 10000 行样例数据、字段兼容和清洗报告
3. Dashboard：展示图表与“数据发现”结论
4. Visual Explorer：演示筛选条件变化后的图表反馈
5. Data Q&A：提问“Indie 游戏价格主要集中在哪？”
6. Idea Lab：输入创意并展示 PLUS 创新分析结果

## 相关文档

- `docs/提交验收清单.md`
- `docs/代码来源标注.md`
- `docs/AI使用说明书.md`
- `docs/测试记录.md`
- `docs/数据字典.md`
- `docs/Demo演示脚本.md`

## 常见问题

- 找不到默认数据：检查 `data/sample/sample_steam_games.csv`
- `pytest` 命令不可用：改用 `python3 -m pytest -q` 或 `python -m pytest -q`
- LLM 未配置：属于正常 fallback，不影响大部分演示
- 自定义 CSV 字段较少：系统会保留读取、预览和清洗报告，但部分 Steam 分析会提示受限
