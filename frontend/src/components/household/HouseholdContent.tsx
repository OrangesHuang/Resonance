import { CALLOUT, DataTable, Highlight, Section, Warning } from '../common/ArticleParts'

export default function HouseholdContent() {
  return (
    <article>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">居民 vs 政府：同一场去杠杆，谁在扛</h1>
        <p className="mt-2 text-sm text-gray-400">宏观数据看起来稳，微观体感却很冷——差别不在"借了多少"，而在资产、收入、以及谁能把痛苦往后拖。</p>
      </header>

      <Section id="overview" title="1. 总览：居民缩表 vs 政府扩表">
        <div className={CALLOUT}>
          <Highlight>居民在被迫“缩表”（去杠杆），政府在主动“扩表”（加杠杆）</Highlight>
          <span className="mt-1 block text-gray-400">一个只能硬扛，一个能以时间换空间——这是“资产负债表衰退”（辜朝明框架）的典型症状。</span>
        </div>
        <DataTable
          head={['维度（2026-03）', '中国', '美国']}
          rows={[
            ['居民债务 / GDP', <Highlight>57.5%</Highlight>, '67.2%'],
            ['政府债务 / GDP（2025）', '99.2%', '123%'],
            ['10Y 国债收益率', <Warning>1.678%</Warning>, '4.997%'],
            ['CPI（2026-08）', '0.8%', '3.4%'],
          ]}
        />
        <p className="text-gray-400">注意：中国居民债务/GDP 其实<strong className="text-gray-100">低于美国</strong>，但体感更差——问题在下面三项。</p>
      </Section>

      <Section id="household" title="2. 居民的体感：财富缩、债务重、收入不稳">
        <ol className="list-decimal space-y-2 pl-5">
          <li><strong className="text-gray-100">负财富效应</strong>：家庭财富大头压在<strong className="text-gray-100">房子</strong>上，房价下行 → 账面财富缩水 → 消费收缩、储蓄抬升。</li>
          <li><strong className="text-gray-100">债务-通缩（散户版）</strong>：房贷名义利率 ~3%，CPI 仅 0.8% → <Warning>实际还债成本 ~2.2%</Warning>；抵押物（房子）又在贬值 → 实际债务负担反而上升。</li>
          <li><strong className="text-gray-100">收入端</strong>：就业与收入预期转弱 → 预防性储蓄、<strong className="text-gray-100">提前还贷</strong>（资产/理财收益跑不赢房贷利率）。</li>
          <li><strong className="text-gray-100">体感</strong>：防御、躺平、不买房、低消费、存钱或还贷——<Warning>能做的只有缩表</Warning>。</li>
        </ol>
      </Section>

      <Section id="gov" title="3. 政府的体感：中央从容、地方紧">
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-gray-100">中央</strong>：债务 99%、<Highlight>10Y 收益率仅 1.68%</Highlight>（融资成本极低）、有加杠杆空间 → 体感<Highlight>相对从容</Highlight>，工具是发债 / 化债，但节奏<strong className="text-gray-100">克制</strong>（怕通胀、汇率、道德风险）。</li>
          <li><strong className="text-gray-100">地方</strong>：<Warning>土地财政塌方</Warning>（卖地收入大降）+ 城投债务压顶 → 收入锐减、拖欠、降薪、“过紧日子” → 体感<Warning>紧</Warning>，靠中央化债资金托着。</li>
        </ul>
      </Section>

      <Section id="asymmetry" title="4. 为什么体感割裂（三个不对称）">
        <DataTable
          head={['维度', '居民', '政府']}
          rows={[
            ['目标函数', '收入 / 房价 / 工作', '不崩 / 系统性风险 / 融资功能'],
            ['约束', <Warning>硬（失业即断供）</Warning>, <Highlight>软（r &lt;&lt; g，债务可持续）</Highlight>],
            ['手段', '只能缩表、硬扛', '能加杠杆、平移、以时间换空间'],
          ]}
        />
        <p><strong className="text-gray-100">痛苦的分配是不对称的</strong>：去杠杆的成本被“平移”给了居民和企业（房价不强力托、刺激克制、兜底延迟），居民只能承受。</p>
      </Section>

      <Section id="misread" title="5. 一个容易被误读的数据">
        <div className={CALLOUT}>
          <Highlight>10Y 国债收益率只有 1.68%——这不是“政府信用差”。</Highlight>
          <span className="mt-1 block text-gray-400">
            恰恰相反：它反映的是<strong className="text-gray-100">居民和机构对未来极度悲观、抢着买安全资产（资产荒）</strong>。
            低利率定价的是<Warning>私人部门崩掉的风险偏好</Warning>，而不是公共部门的偿付能力。
          </span>
        </div>
      </Section>

      <Section id="verdict" title="6. 结论">
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-gray-100">宏观数据看起来稳</strong>（政府债务不高、r &lt;&lt; g），<strong className="text-gray-100">微观体感却很冷</strong>（收入、房价、就业）——因为一边在<strong className="text-gray-100">缩表</strong>，一边在<strong className="text-gray-100">扩表</strong>。</li>
          <li>政府的“从容”和居民的“难受”，本质是<Highlight>同一场去杠杆里，谁承担成本的问题</Highlight>。</li>
          <li>这也解释了为什么“名义降息”刺激有限：私人部门在缩表，货币乘数低，通缩与实际利率偏高——<strong className="text-gray-100">钱放出来了，却没人愿意借、愿意花</strong>。</li>
        </ul>
        <p className="text-xs text-gray-600">宏观结构观察，非投资建议；数据来源见「宏观杠杆」页。</p>
      </Section>
    </article>
  )
}
