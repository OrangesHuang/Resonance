import ArticleToc from '../components/common/ArticleToc'
import HouseholdContent from '../components/household/HouseholdContent'
import { HOUSEHOLD_SECTIONS } from '../components/household/sections'

export default function HouseholdGov() {
  return (
    <div className="mx-auto flex max-w-6xl gap-6">
      <aside className="hidden w-56 shrink-0 lg:block">
        <ArticleToc sections={HOUSEHOLD_SECTIONS} />
      </aside>
      <div className="min-w-0 flex-1 rounded-xl border border-gray-800 bg-gray-900/40 p-6">
        <HouseholdContent />
      </div>
    </div>
  )
}
