import { CALLOUT, DataTable, Highlight, Section, Warning } from '../common/ArticleParts'

export default function ResponseContent() {
  return (
    <article>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">实战配置：反弹仓看托底，核心仓看经济</h1>
        <p className="mt-2 text-sm text-gray-400">
          二级市场悲观 = 机会，不是回避理由。战术仓看“有无大资金托底做反弹”；战略仓只认“中国经济实质改善”。
        </p>
      </header>

      <Section id="framework" title="1. 两层仓位框架（不要混为一谈）">
        <DataTable
          head={['层次', '加仓条件', '持仓周期', '依据']}
          rows={[
            ['战术 · 反弹仓', <Highlight>市场悲观 + 大资金托底</Highlight>, '短（做反弹）', '情绪 + 资金'],
            ['战略 · 核心仓', <Highlight>中国经济数据实质改善</Highlight>, '长（趋势持有）', '基本面 + 制度'],
          ]}
        />
        <div className={CALLOUT}>
          <Warning>关键纠偏：</Warning>“二级市场悲观”<strong className="text-gray-100">本身就是买入条件之一</strong>，不是减仓理由；
          真正决定能不能加的是<strong className="text-gray-100">有没有资金托底（反弹）</strong>和<strong className="text-gray-100">经济有没有改善（长线）</strong>。
        </div>
      </Section>

      <Section id="rebound" title="2. 反弹仓：悲观是机会，关键看托底">
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-gray-100">悲观</strong>：位置极低、成交冰冷、情绪绝望——这是<Highlight>赔率的来源</Highlight>。</li>
          <li><strong className="text-gray-100">托底</strong>：悲观之后，必须有<Warning>大资金真金白银进场</Warning>（最可观测的是宽基 ETF 份额净申购，即“国家队脚印”）。</li>
          <li>没有托底的悲观 = 阴跌；有托底的悲观 = 反弹。<strong className="text-gray-100">区别就在这一条。</strong></li>
          <li>案例：2026-07 暴跌，科创50 ETF 单月净申购 <Highlight>+216 亿</Highlight> → 随后 8 月反弹（科创50 +10%、通信 +24%）。</li>
        </ul>
      </Section>

      <Section id="rebound-signal" title="3. 反弹的量化信号（A 股，2026-09）">
        <DataTable
          head={['信号', '当前读数', '含义']}
          rows={[
            ['两市成交额分位', '5.8%', <Highlight>冰点 = 悲观到位</Highlight>],
            ['融资余额分位', '17.5%', '杠杆出清'],
            ['沪深300 60日位置', '9.9%', <Highlight>区间底部</Highlight>],
            ['宽基 ETF 份额净申购', '需持续观察', <Warning>托底证据</Warning>],
          ]}
        />
        <div className={CALLOUT}>
          <Highlight>触发：</Highlight>悲观（低位 + 冰点）<strong className="text-gray-100">且</strong>出现持续大额净申购 → 加反弹仓。
          <span className="mt-1 block text-gray-400">
            注意：底部≠不会更跌（双极致信号 P(20日跌超10%) 11%→13%），所以<Warning>必须带止损</Warning>，赚了就走。
          </span>
        </div>
      </Section>

      <Section id="core" title="4. 长期核心仓：只认中国经济改善">
        <ul className="list-disc space-y-2 pl-5">
          <li>长期投资的核心底层逻辑，<strong className="text-gray-100">必须建立在中国好的经济数据之上</strong>，而不是“跌多了”。</li>
          <li>经济没改善 → 只能做反弹（战术）；经济改善被数据确认 → 才放大<Highlight>长期核心仓</Highlight>。</li>
          <li>这两件事<Warning>不能混</Warning>：把“跌得多”当成“值得长期拿”，是通缩市场里最大的亏损来源。</li>
        </ul>
      </Section>

      <Section id="core-signal" title="5. 五大长期指标（经济实质改善的确认）">
        <DataTable
          head={['#', '指标', '为什么重要', '观察方向']}
          rows={[
            ['1', '垃圾标的去除程度', '壳价值归零、优胜劣汰，市场才有效', '退市常态化、ST/壳股占比下降'],
            ['2', '上市公司造假成本', '提高违规成本 = 保护投资者 / 定价有效', '罚款+刑责+集体诉讼 / 赔偿落地'],
            ['3', '通缩螺旋逆转', '名义增长与企业盈利修复的前提', <Highlight>CPI 站上 2%、PPI 转正、实际利率下行</Highlight>],
            ['4', '消费者信心指数', '需求端修复、内需驱动', '回升至中枢上方并持续'],
            ['5', '就业率', '居民收入与消费的根基', '城镇调查失业率下降、青年失业改善'],
          ]}
        />
        <div className={CALLOUT}>
          <Warning>升级规则：</Warning>上述指标<strong className="text-gray-100">多项同时改善</strong>（尤其 3、4、5 属宏观硬数据，1、2 属制度质量），
          才把仓位从“反弹仓”升级为“长期核心仓”。<strong className="text-gray-100">数据没改善，就始终只做反弹。</strong>
        </div>
      </Section>

      <Section id="alloc" title="6. 配置框架（两层分开）">
        <DataTable
          head={['类别', '比例', '定位']}
          rows={[
            ['现金 / 货币 / 短债', '20–30%', '期权 · 应急 · 弹药'],
            ['海外多资产（QDII / 跨境基金）', '30–40%', '多币种 · 多市场 · 抗通胀'],
            ['黄金', '10%', '抗通胀 · 避险'],
            ['境内反弹仓（战术）', '10–20%', '悲观 + 托底时加，带止损'],
            ['境内长期核心仓（战略）', '0–10%', <Warning>经济数据改善后才放大</Warning>],
          ]}
        />
        <p className="text-gray-400">比例按个人风险承受度调整，仅为框架示意。</p>
      </Section>

      <Section id="summary" title="7. 一句话">
        <div className={CALLOUT}>
          <Highlight>悲观是机会，但要等托底；长线是信心，但要等经济数据。</Highlight>
          <span className="mt-1 block text-gray-400">
            战术仓跟“资金”，战略仓跟“基本面”——<strong className="text-gray-100">别用战术的理由，去做战略的仓位。</strong>
          </span>
        </div>
        <p className="text-xs text-gray-600">框架示意，非投资建议；数据为 2026-09 口径。</p>
      </Section>
    </article>
  )
}
