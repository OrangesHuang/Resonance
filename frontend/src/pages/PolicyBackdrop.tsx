import ArticleToc from '../components/common/ArticleToc'
import PolicyContent from '../components/policy/PolicyContent'
import { POLICY_SECTIONS } from '../components/policy/sections'

export default function PolicyBackdrop() {
  return (
    <div className="mx-auto flex max-w-6xl gap-6">
      <aside className="hidden w-56 shrink-0 lg:block">
        <ArticleToc sections={POLICY_SECTIONS} />
      </aside>
      <div className="min-w-0 flex-1 rounded-xl border border-gray-800 bg-gray-900/40 p-6">
        <PolicyContent />
      </div>
    </div>
  )
}
