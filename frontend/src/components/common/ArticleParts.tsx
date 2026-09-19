import type { ReactNode } from 'react'

export const CALLOUT = 'rounded-lg border border-gray-800 bg-gray-900/60 p-4'

export function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="mb-10 scroll-mt-6">
      <h2 className="mb-4 border-l-2 border-emerald-500 pl-3 text-lg font-bold text-white">{title}</h2>
      <div className="space-y-3 text-sm leading-relaxed text-gray-300">{children}</div>
    </section>
  )
}

export function DataTable({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded border border-gray-800">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-gray-800/60 text-gray-400">
            {head.map((h, i) => (
              <th key={i} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-gray-800/70">
              {r.map((c, j) => (
                <td key={j} className="px-3 py-2 text-gray-300 whitespace-nowrap">{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Highlight({ children }: { children: ReactNode }) {
  return <span className="font-semibold text-emerald-400">{children}</span>
}

export function Warning({ children }: { children: ReactNode }) {
  return <span className="font-semibold text-rose-400">{children}</span>
}
