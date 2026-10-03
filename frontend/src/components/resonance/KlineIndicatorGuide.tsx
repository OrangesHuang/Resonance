interface Row {
  panel: string
  method: string
  read: string
}

const ROWS: Row[] = [
  {
    panel: 'K线主图',
    method: '普通涨跌K线。背景带：淡绿=收盘在年线(MA250)上方(牛)，淡红=下方(熊)；淡绿/淡红竖带=机会/危险共振日；蓝色虚线=当前选中日；B/S=策略买卖点',
    read: '红涨绿跌(A股习惯)；均线 EMA120/EMA350 为长周期价格均线',
  },
  {
    panel: '成交量',
    method: '日成交量柱（灰色）',
    read: '放量=资金参与度高；缩量=观望',
  },
  {
    panel: '份额净申赎(亿份)',
    method: '当日基金总份额变动 = 净申购 − 净赎回（T+1 披露）',
    read: '绿柱=净申购(资金进场/吸筹)，红柱=净赎回(资金离场/卖出)，紫柱=份额折算/合并日(机械变动，非申赎)',
  },
  {
    panel: '综合概率(%)',
    method: '量能/方向/份额三因子 + 价格位置×量能交互，四层门控合成(0–100)',
    read: '≥45 吸筹(绿)，≤35 出货(红)，中间中性；曲线为 0–100 的连续值，45/35 为阈值虚线',
  },
  {
    panel: 'MACD(12,26,9)',
    method: '快慢 EMA(12/26) 之差 DIF，再对其取 EMA(9) 得 DEA，柱=(DIF−DEA)×2',
    read: 'DIF 上穿 DEA(金叉)=动量转多，下穿(死叉)=转空；柱由绿转红=多头增强',
  },
  {
    panel: '主力资金',
    method: '同花顺公式移植：主力进出=EMA(下跌偏离量,3)；吸筹=另一套 Var 系列的 EMA；散户线=100×(55日最高−收盘)/(55日最高−55日最低)；庄家线=EMA(J,6)（RSV(34)→K/D→J）',
    read: '红柱=主力进场、绿柱=洗盘；红柱(吸筹)=吸筹信号；散户线越高=价格越贴近区间低位(散户越少)，80 为强弱分界虚线；紫线(庄家线)上行为庄家动能增强；▼=RSI(3) 自上而下跌破 85 的短线见顶标记',
  },
]

export default function KlineIndicatorGuide() {
  return (
    <details className="bg-gray-900 border border-gray-800 rounded-lg">
      <summary className="cursor-pointer select-none px-4 py-3 text-sm text-gray-400 hover:text-gray-200 transition-colors">
        K线副图指标说明（点击展开）
      </summary>
      <div className="px-4 pb-4">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 pr-3 font-medium whitespace-nowrap">区域</th>
                <th className="text-left py-2 pr-3 font-medium">含义/算法</th>
                <th className="text-left py-2 font-medium">读法</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map(r => (
                <tr key={r.panel} className="border-b border-gray-800/60 last:border-0">
                  <td className="py-2 pr-3 text-gray-300 whitespace-nowrap align-top">{r.panel}</td>
                  <td className="py-2 pr-3 text-gray-400 leading-relaxed">{r.method}</td>
                  <td className="py-2 text-gray-400 leading-relaxed">{r.read}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-[11px] text-gray-500 leading-relaxed">
          提示：副图数值均可在鼠标悬停 K 线时于 tooltip 中查看（含 MACD 的 DIF/DEA/柱、主力资金的四项读数）。
          所有副图与主图共享同一时间轴，缩放/拖动联动。
        </div>
      </div>
    </details>
  )
}
