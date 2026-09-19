import { CALLOUT, DataTable, Highlight, Section, Warning } from '../common/ArticleParts'

export default function MethodologyContent() {
  return (
    <article>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">交易操作框架</h1>
        <p className="mt-2 text-sm text-gray-400">左侧建仓 · 量化择时 · 波动率分层止损——先保本，再择时，后出手。</p>
      </header>

      <Section id="principle" title="0. 总原则">
        <ul className="list-disc space-y-2 pl-5">
          <li><Highlight>本金安全 &gt; 收益</Highlight>：宁可空仓，不做没有赔率的交易。</li>
          <li><Highlight>“空仓”本身是一种仓位</Highlight>：只在赔率显著占优时出手。</li>
          <li>先定义<Highlight>“错在哪里”（证伪线）</Highlight>，再谈“赚多少”。</li>
        </ul>
      </Section>

      <Section id="timing" title="1. 择时：宏观极冷 × 标的极致低位">
        <p className="text-gray-400">触发条件（同时满足）：</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>市场情绪冰点：两市成交额分位 ≤ 20、融资余额分位 ≤ 20；</li>
          <li>市场位置低：沪深300 60日位置处于区间低位；</li>
          <li>标的极致超跌：个券 250日 / 60日价格位置 ≤ 20；</li>
          <li>资金在进：份额净申购（越跌越买，而非赎回）。</li>
        </ul>
        <p className="pt-1 text-gray-400">数据证据（全库 ETF 历史事件研究）：</p>
        <DataTable
          head={['状态', '20日赔率 (p75/p25)', '上行 p75', '下行 p25']}
          rows={[
            ['基准', '1.17', '+4.73%', '−4.03%'],
            ['宏观冷 + 标的极低', <Highlight>1.82</Highlight>, <Highlight>+6.69%</Highlight>, '−3.67%'],
          ]}
        />
        <div className={CALLOUT}>
          关键结论：高赔率来自<Highlight>上行尾部变肥</Highlight>，不是下行消失——P(20日内跌超10%) 由 11% 微升到 13%。
          <span className="mt-1 block text-gray-400">
            所以“高赔率”必须配止损，<Warning>不能理解成“跌不动了”</Warning>。
          </span>
        </div>
        <p className="pt-1 text-gray-400">排除“假机会”（背离）：</p>
        <DataTable
          head={['形态', '20日前向中位', '胜率']}
          rows={[
            ['大盘涨、板块独跌（背离）', <Warning>−0.41%（冷+低位 −1.56%）</Warning>, <Warning>47%（40%）</Warning>],
            ['大盘跌、板块跌（同跌错杀）', '+0.39%', '52%'],
            ['板块显著跑输（rs ≤ −5，系统性错杀）', <Highlight>+1.75%</Highlight>, <Highlight>60%</Highlight>],
          ]}
        />
        <p>只买“<Highlight>跟大盘一起跌、跌过头</Highlight>”的，绝不买“大盘涨、它独跌”的。</p>
      </Section>

      <Section id="cash" title="2. 空仓等待">
        <ul className="list-disc space-y-2 pl-5">
          <li>机构受<strong className="text-gray-100">相对排名 / 规模 / 管理费</strong>约束，被迫持续交易，这是其结构性劣势；个人可主动空仓。</li>
          <li>最优赔率窗口<strong className="text-gray-100">稀少</strong>（宏观冷 + 标的极跌同时出现的机会不多），不值得为平庸机会下注。</li>
          <li>大额现金 = <Highlight>财务退路 + 心理优势</Highlight>，使其能在恐慌中下重仓。</li>
        </ul>
      </Section>

      <Section id="position" title="3. 仓位与成本管理">
        <ul className="list-disc space-y-2 pl-5">
          <li>左侧建仓；上涨<strong className="text-gray-100">一浪减半</strong> → 摊薄成本线下移 → 跌回成本线全清 = 该笔<Highlight>保本</Highlight>。</li>
          <li>已知风险：<Warning>跳空 / 滑点（港股尤甚）</Warning>、“一浪不来”、“卖飞主升”。</li>
          <li>纪律：<strong className="text-gray-100">不加杠杆</strong>；给主升浪留<strong className="text-gray-100">跑者</strong>（三浪减或移动止损）。</li>
          <li>按“最坏情况（跳空穿成本线）”反推<Highlight>总仓位上限</Highlight>——买得起这个错误。</li>
        </ul>
      </Section>

      <Section id="stop" title="4. 止损纪律：按波动率分层">
        <p>固定百分比止损不科学，<Highlight>止损宽度必须随波动率走</Highlight>：</p>
        <DataTable
          head={['分档', '年化波动', '日 σ', '建议止损 ≈ 1.5×日σ']}
          rows={[
            ['老登（上证50 / 红利 / 券商 / 消费）', '16–26%', '~1.4%', '−1.5 ~ −2.5%'],
            ['中登（中证500 / 有色）', '32–42%', '~2.7%', '−3 ~ −4%'],
            ['小登（通信 / 科创芯片）', '48–69%', '~4.2%', '−5 ~ −6.5%'],
          ]}
        />
        <p className="pt-1 text-gray-400">数据依据（双极致信号，5日内）：</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>−1% 止损触发率 <Warning>75%</Warning>，落在噪音带内（太紧）；</li>
          <li>未触发组 <Highlight>+3.75% / 胜率 66%</Highlight> vs 触发组 <Warning>−0.47% / 45%</Warning> → 止损确有信息量；</li>
          <li>改为“<strong className="text-gray-100">收盘确认破位</strong>”后，触发率 75% → <Highlight>58%</Highlight>（过滤影线假摔）。</li>
        </ul>
        <div className={CALLOUT}>
          <strong className="text-gray-100">执行：</strong>收盘确认才止损；高波 / 港股额外防跳空；结构位优先（跌破前低即证伪，立刻认错）。
        </div>
      </Section>

      <Section id="method" title="5. 为什么这套是科学的">
        <ol className="list-decimal space-y-2 pl-5">
          <li><strong className="text-gray-100">事件研究而非个案</strong>：池化历史全部同类事件 + 前向收益分布，避免单次结果过拟合。</li>
          <li><strong className="text-gray-100">用赔率而非胜率评估</strong>：契合“低胜率、高赔率”的左侧交易。</li>
          <li><strong className="text-gray-100">风险优先</strong>：先量化最坏情况（尾部回撤、跳空），据此定仓位与止损。</li>
          <li><strong className="text-gray-100">反人性但有据</strong>：情绪冰点、无人确认时买；热情高涨、共识形成时回避。</li>
          <li><strong className="text-gray-100">可证伪</strong>：每笔都有明确证伪线，不扛单——<Highlight>错得起，才活得久</Highlight>。</li>
        </ol>
      </Section>

      <p className="border-t border-gray-800 pt-4 text-xs text-gray-600">
        以上为个人交易框架梳理，基于历史统计，不构成投资建议。
      </p>
    </article>
  )
}
