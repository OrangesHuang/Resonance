import { useState } from 'react'
import { useAddEtf, useValidateEtfCode } from '../../hooks/useEtfManage'
import type { EtfValidateResult } from '../../api/types'

const INPUT_CLS =
  'bg-gray-950 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 ' +
  'focus:outline-none focus:border-blue-500 disabled:opacity-50'
const BTN_CLS =
  'px-3 py-1.5 rounded text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed'

export default function AddEtfForm({ onAdded }: { onAdded: (code: string, name: string) => void }) {
  const [code, setCode] = useState('')
  const [idx, setIdx] = useState('')
  const [probed, setProbed] = useState<EtfValidateResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const validate = useValidateEtfCode()
  const add = useAddEtf()

  const handleValidate = () => {
    setError(null)
    setProbed(null)
    validate.mutate(code.trim(), {
      onSuccess: (r) => {
        setProbed(r)
        setIdx(r.idx)
      },
      onError: (e: Error) => setError(e.message),
    })
  }

  const handleAdd = () => {
    if (!probed) return
    setError(null)
    add.mutate(
      { code: probed.code, idx: idx.trim() || undefined },
      {
        onSuccess: (r) => {
          setProbed(null)
          setCode('')
          setIdx('')
          onAdded(r.code, r.name)
        },
        onError: (e: Error) => setError(e.message),
      },
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h3 className="text-sm font-medium text-gray-300">添加 ETF</h3>
        <span className="text-[11px] text-gray-500">
          输入 6 位场内基金代码, 自动校验并从行情接口带出名称/交易所
        </span>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <input
          className={`${INPUT_CLS} w-32 font-mono tracking-wider`}
          placeholder="如 159915"
          value={code}
          maxLength={6}
          onChange={(e) => {
            setCode(e.target.value.replace(/\D/g, ''))
            setProbed(null)
            setError(null)
          }}
          onKeyDown={(e) => e.key === 'Enter' && code.length === 6 && handleValidate()}
        />
        <button
          className={`${BTN_CLS} bg-gray-800 text-gray-200 hover:bg-gray-700`}
          disabled={code.length !== 6 || validate.isPending}
          onClick={handleValidate}
        >
          {validate.isPending ? '校验中…' : '校验'}
        </button>

        {probed && (
          <>
            <span className="text-sm text-gray-300">
              {probed.name}
              <span className="ml-2 text-xs text-gray-500">
                {probed.market === 'sh' ? '上交所' : '深交所'}
              </span>
            </span>
            <input
              className={`${INPUT_CLS} w-44`}
              placeholder="指数名标签"
              value={idx}
              onChange={(e) => setIdx(e.target.value)}
            />
            <button
              className={`${BTN_CLS} bg-blue-600 text-white hover:bg-blue-500`}
              disabled={add.isPending}
              onClick={handleAdd}
            >
              {add.isPending ? '添加中…' : '确认添加'}
            </button>
          </>
        )}
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
