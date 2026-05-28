# AI 使用说明书

## AI 使用原则

AI 是辅助工具，不是项目负责人。项目主题、功能取舍、课程展示路径和最终判断由学生负责。AI 生成的代码、文档和分析模板必须经过本地运行、测试和人工检查。

## AI 使用环节

- 需求拆解
- 代码生成
- Debug
- 前端 UI 改造
- 图表设计
- 数据问答模板
- LLM 报告生成
- README 整理

## 关键使用案例

### 案例名称：项目需求拆解与 V2 重构方向确定

任务目标：将原 Streamlit 思路重构为 FastAPI + HTML/CSS/JavaScript 的 Web 程序。

Prompt 摘要：要求从零重写 GameScope_V2，并按 5 个阶段实现课程五模块和 PLUS 创新。

AI 返回内容摘要：拆分为项目骨架、数据底座、前端可视化、Q&A/Idea Lab、文档测试五个阶段。

学生如何修改 / 验证：确认不使用 Streamlit、React、Vue、Vite，保留 Python 数据分析作为核心。

最终结果：形成清晰的 V2 技术路线和阶段交付计划。

### 案例名称：数据清洗函数生成与字段兼容修正

任务目标：实现 CSV 读取、字段名映射、缺失值处理、评论数和好评率计算。

Prompt 摘要：要求兼容 Name、Release date、Positive、Negative 等常见字段名。

AI 返回内容摘要：生成 `clean_steam_data`、`add_derived_features`、字段标准化工具函数。

学生如何修改 / 验证：通过 pytest 检查 total_reviews、positive_rate、release_year、is_indie 等衍生字段。

最终结果：上传字段不完整 CSV 时系统尽量兼容，不会直接崩溃。

### 案例名称：Dashboard 图表设计与前端实现

任务目标：让市场总览页面展示核心指标和 ECharts 图表。

Prompt 摘要：要求展示发行趋势、类型 Top 10、标签 Top 20、价格分布、好评率分布。

AI 返回内容摘要：生成 Dashboard API 调用、指标卡、折线图、柱状图和空状态处理。

学生如何修改 / 验证：本地启动 FastAPI，上传 CSV 后检查图表标题、数据和页面稳定性。

最终结果：Dashboard 可用于展示数据分析和数据可视化模块。

### 案例名称：竞品雷达相似度函数实现

任务目标：根据创意画像寻找相似竞品，并解释相似原因。

Prompt 摘要：相似度由 genre similarity、tag similarity、price similarity、keyword similarity 组成。

AI 返回内容摘要：生成 `find_similar_games`，输出 similarity_score 和 match_reason。

学生如何修改 / 验证：检查分数在 0-100 范围内，match_reason 包含共同类型、共同标签或价格接近。

最终结果：Idea Lab 能展示相似竞品表格和竞品相似度图。

### 案例名称：Opportunity Score 五维评分设计

任务目标：设计课堂可解释的五维机会评分。

Prompt 摘要：要求包含热度、口碑、趋势、竞争压力、差异化空间。

AI 返回内容摘要：生成 `calculate_opportunity_score`，每个维度包含 score、explanation、evidence。

学生如何修改 / 验证：确认 LLM 不参与评分计算，结论加入“仅作为早期立项参考”的边界声明。

最终结果：Idea Lab 能输出总分和五维拆解，适合 3 分钟 Demo 讲清楚。

### 案例名称：LLM fallback 设计

任务目标：没有 API Key 时项目仍可完整运行。

Prompt 摘要：要求环境变量配置 DEEPSEEK_API_KEY、LLM_BASE_URL、LLM_MODEL，失败不崩溃。

AI 返回内容摘要：生成 `get_llm_status` 和 `safe_call_llm`。

学生如何修改 / 验证：删除环境变量后运行测试，确认返回 Rule-based fallback。

最终结果：课堂演示不依赖外部 LLM 服务。

### 案例名称：README 与 Demo 脚本整理

任务目标：生成可提交、可复现、可演示的说明文档。

Prompt 摘要：要求 README、AI 使用说明、数据字典、测试记录、3 分钟 Demo 脚本。

AI 返回内容摘要：生成文档初稿和课程要求检查表。

学生如何修改 / 验证：按本地实际运行命令和测试结果修正说明。

最终结果：项目达到课程提交状态。

## AI 能力边界

- 擅长局部代码生成。
- 擅长解释报错。
- 擅长生成文档初稿。
- 不擅长完整系统全局规划，需要学生先明确目标。
- 不保证生成代码一次本地运行成功。
- 容易生成脱离数据的漂亮话。
- 需要人工检查分析指标是否有业务意义。

## 学生关键贡献

- 选择游戏市场分析主题。
- 确定独立游戏开发者为核心用户。
- 决定 V2 改成 HTML/CSS/JS + FastAPI。
- 确定 PLUS 主线为创意输入、竞品雷达、机会评分、差异化建议。
- 决定 AI 不参与计算，只参与解析和解释。
- 检查代码运行结果。
- 设计课堂 Demo 路径。

## 反思总结

AI 提升效率的地方：能快速生成模块骨架、重复性接口、测试样例和文档初稿。

AI 容易误导的地方：可能为了表达完整而生成未验证的结论，或把 LLM 当作计算来源。

如何判断 AI 输出是否可靠：必须看代码是否能运行、测试是否覆盖关键规则、数据结论是否来自后端函数。

如果重做一次，会先准备更完整的 Steam 样例数据，再让 AI 围绕固定数据字典生成分析函数和 Demo 路径。
