export function renderHome() {
  return `
    <section class="section">
      <div class="hero">
        <div>
          <p class="eyebrow">Steam 市场智能分析</p>
          <h2>GameScope</h2>
        </div>
        <p class="hero-subtitle">面向独立游戏创意的 Steam 市场分析平台</p>
        <p class="hero-copy">输入一个游戏创意，系统将基于 Steam 数据分析相似竞品、市场机会和差异化方向。V2 使用 FastAPI 后端保留 Python 数据分析能力，用 HTML/CSS/JavaScript 呈现更稳定的课堂演示。</p>
        <div>
          <button class="primary-button" data-action="start-scan">开始市场扫描</button>
        </div>
      </div>

      <div class="grid-4">
        <article class="card">
          <h3>竞品雷达</h3>
          <p>根据类型、标签、价格和关键词寻找相似竞品，并解释匹配原因。</p>
        </article>
        <article class="card">
          <h3>机会评分</h3>
          <p>从热度、口碑、趋势、竞争压力和差异化空间评估立项机会。</p>
        </article>
        <article class="card">
          <h3>差异化洞察</h3>
          <p>结合竞品高频标签和创意关键词生成差异化建议卡片。</p>
        </article>
        <article class="card">
          <h3>数据问答</h3>
          <p>用规则问答和可选 LLM 解释回答市场分析问题，避免凭空编造数据。</p>
        </article>
      </div>

      <div class="card">
        <h3>课程模块映射</h3>
        <div class="module-strip">
          <span class="module-chip">数据读取</span>
          <span class="module-chip">数据预处理</span>
          <span class="module-chip">数据分析</span>
          <span class="module-chip">数据可视化</span>
          <span class="module-chip">交互式问答</span>
          <span class="module-chip">PLUS 创新</span>
        </div>
      </div>
    </section>
  `;
}
