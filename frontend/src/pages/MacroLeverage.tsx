import ArticleToc from '../components/common/ArticleToc'
import MacroContent from '../components/macro/MacroContent'
import { MACRO_SECTIONS } from '../components/macro/sections'

export default function MacroLeverage() {
  return (
    <div className="mx-auto flex max-w-6xl gap-6">
      <aside className="hidden w-56 shrink-0 lg:block">
        <ArticleToc sections={MACRO_SECTIONS} />
      </aside>
      <div className="min-w-0 flex-1 rounded-xl border border-gray-800 bg-gray-900/40 p-6">
        <MacroContent />
      </div>
    </div>
  )
}
