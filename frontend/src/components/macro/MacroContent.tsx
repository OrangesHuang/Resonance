import { CALLOUT, DataTable, Highlight, Section, Warning } from '../common/ArticleParts'

export default function MacroContent() {
  return (
    <article>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">中国 vs 美国：负债率、实际利率与杠杆程度</h1>
        <p className="mt-2 text-sm text-gray-400">判断一个经济体的杠杆风险，不能只看政府债务——要同时看总杠杆、实际利率、r 与 g、以及币种。</p>
      </header>

      <Section id="data" title="1. 硬数据对比">
        <DataTable
          head={['指标', '中国', '美国']}
          rows={[
            ['政府债务 / GDP（2025, IMF）', <Highlight>99.2%</Highlight>, <Highlight>123%</Highlight>],
            ['CPI 通胀（2026-08, YoY）', '0.8%', '3.4%'],
            ['政策利率（2026-09）', '3.00%（LPR 1Y）', '4.00%（联邦基金）'],
            ['10Y 国债收益率（09-18）', '1.678%', '4.997%'],
            ['GDP 环比增速（2026Q2）', '0.9%', '1.5%'],
            ['总杠杆（非金融债务 / GDP, BIS 近似）', <Warning>~300%+</Warning>, '~250–260%'],
          ]}
        />
        <p className="text-gray-400">政府口径：美国更高。但这不是全貌——真正决定风险的是下面三项。</p>
      </Section>

      <Section id="real-rate" title="2. 实际利率（名义 − 通胀）">
        <DataTable
          head={['口径', '中国', '美国']}
          rows={[
            ['实际政策利率', <Highlight>+2.20%</Highlight>, '+0.60%'],
            ['实际 10Y 利率', '+0.88%', <Highlight>+1.60%</Highlight>],
          ]}
        />
        <div className={CALLOUT}>
          <Warning>最反直觉、也最关键：</Warning>中国<strong className="text-gray-100">名义利率低，但通胀更低</strong>，所以
          <Highlight>实际政策利率（+2.2%）反而比美国（+0.6%）更高</Highlight>。
          <span className="mt-1 block text-gray-400">美国名义 5% 看着吓人，减掉 3.4% 通胀，实际并不高。</span>
        </div>
      </Section>

      <Section id="leverage" title="3. 杠杆程度判断（别只看政府债务）">
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-gray-100">政府口径</strong>：美国 123% &gt; 中国 99%，美国更高。</li>
          <li><strong className="text-gray-100">总杠杆（宏观杠杆率）</strong>：中国约 <Warning>300%+</Warning>，美国约 250–260%，<Warning>中国更高</Warning>。</li>
          <li><strong className="text-gray-100">结构完全不同</strong>：
            <br />· 中国——杠杆在 <Highlight>企业 + 地方（城投/LGFV）+ 居民（房贷）</Highlight>，政府明面反而不高，<strong className="text-gray-100">隐性债务是核心</strong>；
            <br />· 美国——杠杆在 <Highlight>联邦政府</Highlight>，企业 / 居民相对健康。</li>
        </ul>
      </Section>

      <Section id="sustainability" title="4. 可持续性：r vs g，以及币种">
        <DataTable
          head={['维度', '中国', '美国']}
          rows={[
            ['10Y 利率 r', '1.68%', '5.0%'],
            ['名义增长 g（≈实际+通胀）', '~4.5–5.8%', '~5%'],
            ['r − g', <Highlight>r 远小于 g</Highlight>, <Warning>r ≈ g（紧平衡）</Warning>],
            ['债务币种 / 债主', '本币 / 主要国内', '储备货币 / 全球需求'],
          ]}
        />
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-gray-100">中国</strong>：融资成本极低（r &lt;&lt; g），政府债务<Highlight>可持续</Highlight>；且本币、债主在国内，<strong className="text-gray-100">外部挤兑风险小</strong>。</li>
          <li><strong className="text-gray-100">美国</strong>：r ≈ g，<Warning>增长一放缓，债务/GDP 就滚雪球</Warning>；靠<strong className="text-gray-100">储备货币 + 全球储值需求</strong>续命，赤字大、必须不断再融资。</li>
        </ul>
      </Section>

      <Section id="verdict" title="5. 结论：两种完全不同的“杠杆病”">
        <ul className="list-disc space-y-2 pl-5">
          <li><Warning>中国 = 高总杠杆 + 高实际利率 + 通缩</Warning>：真痛点是<strong className="text-gray-100">债务-通缩螺旋</strong>——名义利率再低也追不上更低的通胀，实际利率偏高，压制去杠杆，城投 / 地产是雷区。但政府明面债务不高、r &lt;&lt; g、币种自主，属于<Highlight>“痛而不崩”</Highlight>。</li>
          <li><Warning>美国 = 政府高债务 + 名义高利率 + r ≈ g</Warning>：靠<strong className="text-gray-100">霸权货币</strong>续命，缺点是财政赤字大、必须持续再融资，一旦增长 / 通胀回落，债务/GDP 会快速上升。</li>
          <li><strong className="text-gray-100">一句话</strong>：论“政府借得多”，美国更狠（123%）；论“整个经济体的杠杆压力”，中国更重（总杠杆 300%+、实际利率更高、又在通缩）。</li>
        </ul>
        <div className={CALLOUT}>
          <Highlight>中国是“高杠杆 + 通缩”的慢性病，美国是“高债务 + 靠霸权续命”的慢性病——都不是健康状态，但病理完全不同。</Highlight>
        </div>
      </Section>

      <Section id="source" title="6. 数据来源与口径">
        <ul className="list-disc space-y-2 pl-5 text-gray-400">
          <li>政府债务/GDP：IMF（2025 年值，TradingEconomics 转载）；</li>
          <li>CPI 通胀：2026-08 同比；政策利率：2026-09（中国 LPR 1Y / 美国联邦基金）；</li>
          <li>10Y 国债收益率：2026-09-18；GDP 环比：2026Q2；</li>
          <li>总杠杆（非金融部门债务/GDP）为 BIS 口径近似值，非实时精确值。</li>
        </ul>
        <p className="text-xs text-gray-600">宏观结构分析，非投资建议。</p>
      </Section>
    </article>
  )
}
