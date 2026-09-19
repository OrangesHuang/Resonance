import ArticleToc from '../components/common/ArticleToc'
import MethodologyContent from '../components/methodology/MethodologyContent'
import { METHODOLOGY_SECTIONS } from '../components/methodology/sections'

export default function Methodology() {
  return (
    <div className="mx-auto flex max-w-6xl gap-6">
      <aside className="hidden w-56 shrink-0 lg:block">
        <ArticleToc sections={METHODOLOGY_SECTIONS} />
      </aside>
      <div className="min-w-0 flex-1 rounded-xl border border-gray-800 bg-gray-900/40 p-6">
        <MethodologyContent />
      </div>
    </div>
  )
}
