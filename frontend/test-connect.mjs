import * as echarts from 'echarts'

const dates = Array.from({length: 100}, (_, i) => `2026-${String(i).padStart(4,'0')}`)

const a = echarts.init(null, null, { renderer: 'svg', ssr: true, width: 800, height: 520 })
const b = echarts.init(null, null, { renderer: 'svg', ssr: true, width: 800, height: 420 })

// KlineChart-like: 2 grids, dataZoom xAxisIndex [0,1]
a.setOption({
  animation: false,
  grid: [{ top: 20, height: '58%' }, { top: '76%', height: '14%' }],
  xAxis: [
    { type: 'category', data: dates, gridIndex: 0, boundaryGap: true },
    { type: 'category', data: dates, gridIndex: 1, boundaryGap: true },
  ],
  yAxis: [{ scale: true, gridIndex: 0 }, { scale: true, gridIndex: 1 }],
  series: [
    { type: 'candlestick', data: dates.map(() => [1,2,0.5,2.5]), xAxisIndex: 0, yAxisIndex: 0 },
    { type: 'bar', data: dates.map(() => 10), xAxisIndex: 1, yAxisIndex: 1 },
  ],
  dataZoom: [
    { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
    { type: 'slider', xAxisIndex: [0, 1], start: 0, end: 100 },
  ],
})

// SignalHistoryChart-like: 2 grids, line + bar panes
b.setOption({
  animation: false,
  grid: [{ top: 30, height: '52%' }, { top: '70%', height: '14%' }],
  xAxis: [
    { type: 'category', data: dates, boundaryGap: false },
    { type: 'category', data: dates, gridIndex: 1, boundaryGap: true },
  ],
  yAxis: [{ min: 0, max: 100 }, { min: 0, max: 100, gridIndex: 1 }],
  series: [
    { type: 'line', data: dates.map(() => 50), xAxisIndex: 0, yAxisIndex: 0 },
    { type: 'bar', data: dates.map(() => ({ value: 60 })), xAxisIndex: 1, yAxisIndex: 1 },
  ],
  dataZoom: [
    { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
    { type: 'slider', xAxisIndex: [0, 1], start: 0, end: 100 },
  ],
})

a.group = 'g'; b.group = 'g'
echarts.connect('g')

// simulate wheel-zoom on chart A's inside zoom
a.dispatchAction({ type: 'datazoom', dataZoomIndex: 0, start: 20, end: 80 })

const bZooms = b.getOption().dataZoom
console.log('after A inside-zoom -> B windows:', bZooms.map(z => `${z.start}/${z.end}`).join(', '))

// simulate slider drag on chart A
a.dispatchAction({ type: 'datazoom', dataZoomIndex: 1, start: 30, end: 70 })
const bZooms2 = b.getOption().dataZoom
console.log('after A slider-zoom -> B windows:', bZooms2.map(z => `${z.start}/${z.end}`).join(', '))

// reverse: zoom from B, check A
b.dispatchAction({ type: 'datazoom', dataZoomIndex: 0, start: 10, end: 60 })
const aZooms = a.getOption().dataZoom
console.log('after B inside-zoom -> A windows:', aZooms.map(z => `${z.start}/${z.end}`).join(', '))
