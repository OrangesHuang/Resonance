import { useCallback } from 'react'
import * as echarts from 'echarts'

/** 同轴图表缩放原生联动组: 组内任意图 dataZoom 变化, 其余图自动同步。
 *  注意: 组内所有图 x 轴数据(日期序列)必须一致, 否则缩放错位。 */
export const RESONANCE_SYNC_GROUP = 'resonance-sync'
export const SENTIMENT_SYNC_GROUP = 'sentiment-sync'

export function useChartSync(groupId: string) {
  const onChartReady = useCallback((inst: echarts.ECharts) => {
    inst.group = groupId
    echarts.connect(groupId)
  }, [groupId])

  return onChartReady
}
