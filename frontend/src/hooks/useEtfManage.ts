import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { addEtf, deleteEtf, fetchEtfManageList, validateEtfCode } from '../api/client'
import { cacheClear } from '../utils/idbCache'

// 清单增删影响面广: ['etfList'] 在共振/对比页是 staleTime Infinity, 必须显式失效
const UNIVERSE_KEYS = [
  ['etfList'],
  ['etfManage'],
  ['data'],
  ['signals'],
  ['realtime'],
  ['strategyVersions'],
  ['portfolioBacktest'],
  ['resonance'],
  ['etfHistory'],
]

function invalidateUniverse(qc: QueryClient) {
  for (const key of UNIVERSE_KEYS) qc.invalidateQueries({ queryKey: key })
  void cacheClear().catch(() => {})  // 清 IndexedDB 中按 code 缓存的孤儿数据
}

export function useEtfManageList() {
  return useQuery({
    queryKey: ['etfManage'],
    queryFn: fetchEtfManageList,
  })
}

export function useValidateEtfCode() {
  return useMutation({
    mutationFn: (code: string) => validateEtfCode(code),
  })
}

export function useAddEtf() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { code: string; idx?: string }) => addEtf(body),
    onSuccess: () => invalidateUniverse(queryClient),
  })
}

export function useDeleteEtf() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => deleteEtf(code),
    onSuccess: () => invalidateUniverse(queryClient),
  })
}
