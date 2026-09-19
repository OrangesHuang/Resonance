import ArticleToc from '../components/common/ArticleToc'
import ResponseContent from '../components/response/ResponseContent'
import { RESPONSE_SECTIONS } from '../components/response/sections'

export default function Response() {
  return (
    <div className="mx-auto flex max-w-6xl gap-6">
      <aside className="hidden w-56 shrink-0 lg:block">
        <ArticleToc sections={RESPONSE_SECTIONS} />
      </aside>
      <div className="min-w-0 flex-1 rounded-xl border border-gray-800 bg-gray-900/40 p-6">
        <ResponseContent />
      </div>
    </div>
  )
}
