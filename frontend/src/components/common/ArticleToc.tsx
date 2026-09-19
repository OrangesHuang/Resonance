export interface TocItem {
  id: string
  label: string
}

export default function ArticleToc({ sections }: { sections: TocItem[] }) {
  return (
    <nav className="sticky top-6 space-y-1 text-sm">
      <p className="px-3 pb-2 text-xs uppercase tracking-wider text-gray-500">目录</p>
      {sections.map(s => (
        <a
          key={s.id}
          href={`#${s.id}`}
          className="block px-3 py-2 rounded text-gray-400 hover:text-white hover:bg-gray-800/50 transition-colors"
        >
          {s.label}
        </a>
      ))}
    </nav>
  )
}
