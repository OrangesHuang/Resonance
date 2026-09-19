import ArticleToc from '../components/common/ArticleToc'
import RealRateContent from '../components/realrate/RealRateContent'
import { REALRATE_SECTIONS } from '../components/realrate/sections'

export default function RealRate() {
  return (
    <div className="mx-auto flex max-w-6xl gap-6">
      <aside className="hidden w-56 shrink-0 lg:block">
        <ArticleToc sections={REALRATE_SECTIONS} />
      </aside>
      <div className="min-w-0 flex-1 rounded-xl border border-gray-800 bg-gray-900/40 p-6">
        <RealRateContent />
      </div>
    </div>
  )
}
