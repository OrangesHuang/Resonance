import { CALLOUT, DataTable, Highlight, Section, Warning } from '../common/ArticleParts'

export default function PolicyContent() {
  return (
    <article>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">政策底色与庄家博弈</h1>
        <p className="mt-2 text-sm text-gray-400">市场的真实底色：不是价值发现，是筹码再分配。看清规则，才能不站在被收割的一边。</p>
      </header>

      <Section id="nature" title="1. 市场真实底色">
        <ul className="list-disc space-y-2 pl-5">
          <li>短期看，市场是<strong className="text-gray-100">筹码从一双手转移到另一双手</strong>的地方，价格只是转移的记账符号。</li>
          <li>扣除分红和交易成本，博弈接近<Highlight>零和 / 负和</Highlight>——你赚的，正是别人亏的。</li>
          <li>食物链决定谁赚谁亏：<Highlight>信息、资金、耐心</Highlight>都在顶端的那批人，赚的就是这三样都缺的那批人。</li>
          <li>所以“价值投资”是少数人的叙事，<Warning>筹码转移才是每天的真相</Warning>。</li>
        </ul>
      </Section>

      <Section id="whale" title="2. 食物链顶端：最大的逆周期玩家">
        <p>国家队（汇金 / 证金 / 社保等）是市场上<Highlight>唯一“弹药近乎无限 + 信息全知 + 逆周期”</Highlight>的玩家。</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>它的动作**可观测**：恐慌时通过宽基 ETF **大额净申购**托底。</li>
          <li>它<Warning>不追涨、不接盘</Warning>；只做两件事——<strong className="text-gray-100">别人割肉时接、别人追高时退</strong>。</li>
        </ul>
        <DataTable
          head={['时点', '它的行为', '数据（ETF 份额）']}
          rows={[
            ['2026-07 暴跌', '逆势大额净申购（托底）', <Highlight>科创50 ETF 单月 +216 亿</Highlight>],
            ['2026-08 反弹', '市场自行修复', '科创50 +10%、通信设备 +24%'],
          ]}
        />
        <p className="text-gray-400">底部有它当对手盘，高位却没有它——这就是“政策底”与“政策顶”的不对称。</p>
      </Section>

      <Section id="narrative" title="3. “平准”叙事：给收割一个公益名分">
        <ul className="list-disc space-y-2 pl-5">
          <li>同样的“低位买、高位卖”：普通资金叫 <Warning>高抛低吸 / 割韭菜</Warning>，它叫 <Highlight>平准 / 稳定市场</Highlight>。</li>
          <li><strong className="text-gray-100">行为一模一样，名分天差地别。</strong>“公益”这个名头，是它最大的护城河——有它才能“站着把钱挣了”。</li>
          <li>它不是好人，也不是坏人，它是<Highlight>利益最大化的巨鲸</Highlight>；只是它手里多了一张“合法收割”的牌照。</li>
          <li>动机是复合的（防系统性风险 / 国资市值 / <strong className="text-gray-100">融资功能</strong> / 社会信心），<strong className="text-gray-100">但都指向同一动作：托底、退高</strong>。</li>
        </ul>
        <div className={CALLOUT}>
          <Warning>残酷真相：</Warning>市场崩了 IPO / 再融资就发不出去。所谓“平准”，很大程度是<strong className="text-gray-100">为了让市场的融资功能继续运转</strong>——顺便，它也把差价赚了。
        </div>
      </Section>

      <Section id="game" title="4. 最残酷的庄家博弈逻辑">
        <ol className="list-decimal space-y-2 pl-5">
          <li><strong className="text-gray-100">它必须撑场</strong>（崩了它更麻烦）——这是它唯一“被迫”的动作，<Highlight>你的机会在它被迫买的地方</Highlight>（极致恐慌）。</li>
          <li><strong className="text-gray-100">顶部没有它的买盘</strong>（它只会退、不会追）——顶是杠杆和情绪自己堆的，只能靠杠杆自己瓦解。<Warning>你绝不能在狂热处接盘。</Warning></li>
          <li>散户的两头挨打：<Warning>恐慌时割肉送它便宜筹码，狂热时接它派发的货帮它兑现利润</Warning>。</li>
          <li>结论：<strong className="text-gray-100">跟情绪走 = 稳定亏损；跟脚印走 = 站在它那一边。</strong></li>
        </ol>
      </Section>

      <Section id="evidence" title="5. 数据佐证">
        <p className="text-gray-400">① 背离是垃圾行情——大庄只救系统性错杀，不救特异衰竭：</p>
        <DataTable
          head={['形态', '20日前向中位', '胜率']}
          rows={[
            ['大盘涨、板块独跌（背离）', <Warning>−0.41%（冷+低位 −1.56%）</Warning>, <Warning>47%（40%）</Warning>],
            ['大盘跌、板块跌（同跌错杀）', '+0.39%', '52%'],
            ['板块显著跑输（系统性错杀）', <Highlight>+1.75%</Highlight>, <Highlight>60%</Highlight>],
          ]}
        />
        <p className="pt-1 text-gray-400">② 高赔率来自上行尾部，不是“不会更跌”：</p>
        <DataTable
          head={['状态', '20日赔率', 'P(跌超10%)']}
          rows={[
            ['基准', '1.17', '11%'],
            ['宏观冷 + 标的极低', <Highlight>1.82</Highlight>, <Warning>13%（不降反升）</Warning>],
          ]}
        />
        <p className="pt-1 text-gray-400">③ 影线清洗——大庄用波动把弱手扫出去：</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>−1% 止损 5 日触发率 <Warning>75%</Warning>（落在噪音带内）；</li>
          <li>未触发组 +3.75%/66% vs 触发组 −0.47%/45%——<strong className="text-gray-100">大多数被扫出局的人，是被影线洗掉的。</strong></li>
        </ul>
      </Section>

      <Section id="asymmetry" title="6. 不对称的根源">
        <DataTable
          head={['维度', '大庄', '散户']}
          rows={[
            ['资金', '近乎无限 / 低成本', '有限 / 常带杠杆'],
            ['信息', '全盘视角 / 政策先知', '滞后 / 公开信息'],
            ['规则', '参与制定', '被动遵守'],
            ['问责', '只对上面负责', '自负盈亏'],
            ['时间', '可以等几年', '追涨杀跌'],
            ['情绪', '利用情绪', '被情绪利用'],
          ]}
        />
        <p>散户所有优势里，唯一大庄没有的，是 <Highlight>“可以不玩 / 可以空仓”</Highlight>。</p>
      </Section>

      <Section id="survive" title="7. 幸存者的路">
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-gray-100">不跟情绪，跟脚印</strong>：ETF 份额净申购 / 净赎回 = 它的口供（每日公开，比它自报更可信）。</li>
          <li><strong className="text-gray-100">在它被迫买的地方同向</strong>：极致悲观 + 宏观冷 + 跌幅到位。</li>
          <li><strong className="text-gray-100">在它退的地方离场</strong>：高位 + 份额转净赎回 + 情绪狂热。</li>
          <li><strong className="text-gray-100">保本 &gt; 收益</strong>：空仓、非对称下注、波动率分层止损——买得起错误。</li>
          <li><strong className="text-gray-100">别相信叙事</strong>：名字是它给的，脚印是它藏不住的。</li>
        </ul>
        <div className={CALLOUT}>
          <Highlight>市场不会公平，但你可以不站在被收割的一边。</Highlight>
        </div>
      </Section>

      <p className="border-t border-gray-800 pt-4 text-xs text-gray-600">
        以上为市场结构观察与个人观点，基于历史统计，不构成投资建议，亦不针对任何具体机构或个人。
      </p>
    </article>
  )
}
