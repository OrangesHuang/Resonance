const ROWS = [
  { name: '价格位置', method: '(当日收盘 − 60日最低) / (60日最高 − 60日最低) × 100，高低点取自K线', red: '≥70 高位', green: '≤40 低位' },
  { name: '份额流向', method: '当日份额变动率(%) 经分段线性映射为份额概率(0-100)', red: '≤30 净赎回', green: '≥65 净申购' },
  { name: '交易方向', method: '量比(当日成交量/20日均量)≥1.5 放量时：位置≤40吸筹、≥70出货，否则中性', red: '出货', green: '吸筹' },
  { name: '成交额热度', method: '两市成交额经 MA5 平滑后，滚动 60 个交易日分位', red: '≥80 分位 过热', green: '≤20 分位 冷清' },
  { name: '融资杠杆', method: '融资余额滚动 60 个交易日分位', red: '≥80 分位 过热', green: '≤20 分位 冷清' },
]

export default function ResonanceMethodNote() {
  return (
    <details className="bg-gray-900 border border-gray-800 rounded-lg">
      <summary className="cursor-pointer select-none px-4 py-3 text-sm text-gray-400 hover:text-gray-200 transition-colors">
        指标计算方法与阈值说明（点击展开）
      </summary>
      <div className="px-4 pb-4">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 pr-3 font-medium whitespace-nowrap">指标</th>
                <th className="text-left py-2 pr-3 font-medium">计算方法</th>
                <th className="text-left py-2 pr-3 font-medium whitespace-nowrap">红灯(风险)</th>
                <th className="text-left py-2 font-medium whitespace-nowrap">绿灯(机会)</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map(r => (
                <tr key={r.name} className="border-b border-gray-800/60 last:border-0">
                  <td className="py-2 pr-3 text-gray-300 whitespace-nowrap align-top">{r.name}</td>
                  <td className="py-2 pr-3 text-gray-400 leading-relaxed">{r.method}</td>
                  <td className="py-2 pr-3 text-red-400 whitespace-nowrap align-top">{r.red}</td>
                  <td className="py-2 text-green-400 whitespace-nowrap align-top">{r.green}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-[11px] text-gray-500 leading-relaxed">
          分位数算法：分位 = (窗口内低于当日的天数 + 0.5 × 相等的天数) / 窗口样本数 × 100；窗口为滚动 60 个交易日，样本不足 20 个时不计算（记为灰灯）。
          成交额热度先对两市成交额做 5 日均线(MA5)平滑再计算分位，与「市场情绪」页分区口径一致。
          共振判定：同色灯 ≥3 盏 → 危险共振(红)/机会共振(绿)，否则中性。红灯=出货/过热风险，绿灯=吸筹/冷清机会，灰灯=中性或数据缺失。
        </div>
      </div>
    </details>
  )
}
