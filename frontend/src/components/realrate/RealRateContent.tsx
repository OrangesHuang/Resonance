import { CALLOUT, DataTable, Highlight, Section, Warning } from '../common/ArticleParts'

function Formula({ children }: { children: string }) {
  return (
    <div className="whitespace-pre-line rounded-lg border border-gray-800 bg-gray-950/70 px-4 py-3 font-mono text-xs text-emerald-300">
      {children}
    </div>
  )
}

export default function RealRateContent() {
  return (
    <article>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">实际利率：怎么算，以及为什么"名义低"反而"实际高"</h1>
        <p className="mt-2 text-sm text-gray-400">拆解 +2.2%（中国）vs +0.6%（美国）的来源，并说明这个数字对口径有多敏感。</p>
      </header>

      <Section id="formula" title="1. 公式：费雪方程">
        <p>实际利率衡量的是<Highlight>资金的真实施加成本</Highlight>，要把通胀从名义利率里剔除：</p>
        <Formula>实际利率 ≈ 名义利率 − 通胀率</Formula>
        <p className="text-gray-400">精确版（费雪方程）：</p>
        <Formula>{'(1 + 名义利率) = (1 + 实际利率) × (1 + 通胀率)\n→ 实际利率 = (1 + 名义利率) / (1 + 通胀率) − 1'}</Formula>
      </Section>

      <Section id="inputs" title="2. 输入取值">
        <DataTable
          head={['输入', '中国', '美国']}
          rows={[
            ['名义政策利率', 'LPR 1Y = 3.00%', '联邦基金 = 4.00%'],
            ['通胀（CPI 同比，2026-08）', '0.8%', '3.4%'],
          ]}
        />
      </Section>

      <Section id="calc" title="3. 计算过程">
        <p className="text-gray-400">近似式：</p>
        <ul className="list-disc space-y-1 pl-5 font-mono text-xs text-gray-300">
          <li>中国：3.00% − 0.8% = <Highlight>+2.20%</Highlight></li>
          <li>美国：4.00% − 3.4% = <Highlight>+0.60%</Highlight></li>
        </ul>
        <p className="text-gray-400">精确式（费雪）：</p>
        <ul className="list-disc space-y-1 pl-5 font-mono text-xs text-gray-300">
          <li>中国：(1.03 ÷ 1.008) − 1 = +2.18%</li>
          <li>美国：(1.04 ÷ 1.034) − 1 = +0.58%</li>
        </ul>
        <p className="text-gray-400">两者几乎一致——<strong className="text-gray-100">利率低、通胀低时，近似式误差可忽略</strong>。</p>
      </Section>

      <Section id="intuition" title="4. 直觉：名义利率 ≠ 真实资金成本">
        <p>名义利率只是"账面利息"，通胀会<Highlight>侵蚀货币购买力</Highlight>：</p>
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-gray-100">美国</strong>：拿 4% 利息，物价涨 3.4% → 购买力只多了 <Warning>0.6%</Warning>；</li>
          <li><strong className="text-gray-100">中国</strong>：拿 3% 利息，物价只涨 0.8% → 购买力多了 <Highlight>2.2%</Highlight>。</li>
        </ul>
        <div className={CALLOUT}>
          所以中国<strong className="text-gray-100">不是"利率低"，而是"通胀更低"（接近通缩）</strong>——低通胀把名义低利率"顶"成了偏高的实际利率。
        </div>
      </Section>

      <Section id="deflation" title="5. 为什么重要：债务-通缩">
        <ul className="list-disc space-y-2 pl-5">
          <li>实际利率高 = <Highlight>借钱的真实代价大</Highlight> → 企业/居民还债负担重、不敢借贷消费；</li>
          <li>需求更弱 → 通胀更低 → <Warning>实际利率更高</Warning>……形成自我强化的<strong className="text-gray-100">债务-通缩螺旋</strong>（Irving Fisher）；</li>
          <li>这就是为什么中国"降息（名义）"的效果打折——<strong className="text-gray-100">真正卡住需求的是实际利率</strong>。</li>
        </ul>
      </Section>

      <Section id="caveat" title="6. 口径敏感性（这个数字很容易变）">
        <p className="text-gray-400">① 换"政策利率"：</p>
        <DataTable
          head={['口径', '中国实际利率', '美国实际利率']}
          rows={[
            ['用 LPR 1Y（3.0%）', <Highlight>+2.20%</Highlight>, '+0.60%'],
            ['用 7 天逆回购（~1.4%）', <Warning>~+0.60%（与美国接近）</Warning>, '+0.60%'],
          ]}
        />
        <p className="text-gray-400">② 换"通胀"口径：</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>中国 <strong className="text-gray-100">PPI（工业品出厂价）为负</strong> → 用 PPI 算，实际利率<Warning>更高</Warning>；</li>
          <li>美国美联储盯 <strong className="text-gray-100">核心 PCE（约 2.5~3%）</strong>，比 CPI 低 → 按美联储口径，实际利率<Warning>略高</Warning>。</li>
        </ul>
        <p className="text-gray-400">③ 已实现 vs 预期：央行按<strong className="text-gray-100">预期通胀</strong>定利率，这里用的是<strong className="text-gray-100">已实现 CPI</strong>，属"事后"口径，只能当近似。</p>
      </Section>

      <Section id="verdict" title="7. 结论">
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-gray-100">算法</strong>：实际利率 = 名义利率 − 通胀（费雪方程）。</li>
          <li><strong className="text-gray-100">+2.2% vs +0.6%</strong> 是"LPR vs 联邦基金 + CPI"口径下的结果，换口径会变（用 7 天逆回购，中国约 +0.6%，与美国接近）。</li>
          <li><strong className="text-gray-100">但方向是稳的</strong>：中国通胀（0.8%）远低于美国（3.4%）→ <Highlight>同样名义利率下，中国的实际利率一定更高</Highlight>。</li>
        </ul>
        <div className={CALLOUT}>
          <Highlight>看货币政策"松不松"，别只看名义利率，要看实际利率。中国的低名义利率，被更低的通胀抵消甚至反超——这才是"名义宽松、实际偏紧"的本质。</Highlight>
        </div>
        <p className="text-xs text-gray-600">宏观分析，非投资建议；数据口径见「宏观杠杆」页。</p>
      </Section>
    </article>
  )
}
