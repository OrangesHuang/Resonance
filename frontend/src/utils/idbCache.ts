// ETF择时总览 前端缓存: IndexedDB 轻量 KV 封装 + 增量合并工具。
//
// 设计: 历史数据(已收盘 ≥ CACHE_BUFFER_DAYS 前)不可变, 存 IndexedDB;
// 最近 CACHE_BUFFER_DAYS 个交易日可能被修正(T+1份额/复权), 不入缓存,
// 每次以缓存末尾日期(safe_end)为 since 从接口热拉增量。IndexedDB 相比
// localStorage 容量大、异步不卡主线程(全量约 2MB JSON)。
import { CACHE_SCHEMA } from '../api/types'

const DB_NAME = 'etf-resonance-cache'
const DB_VERSION = 1
const STORE = 'kv'

export interface CacheEntry<T> {
  /** 历史数组(升序, 已截断到 endDate) */
  data: T[]
  /** 缓存安全截止日(后端 safe_end): 最近 N 个交易日不入缓存 */
  endDate: string
  /** 写入时间戳(未启用 TTL, 供诊断/清除缓存按钮参考) */
  cachedAt: number
  /** 结构版本: 字段/算法变更时前端 bump, 旧缓存全量失效 */
  schema: number
}

let dbPromise: Promise<IDBDatabase> | null = null

function openDB(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE)
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('IndexedDB open failed'))
  })
  return dbPromise
}

export async function cacheGet<T>(key: string): Promise<CacheEntry<T> | null> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readonly').objectStore(STORE).get(key)
    req.onsuccess = () => resolve((req.result as CacheEntry<T> | undefined) ?? null)
    req.onerror = () => reject(req.error ?? new Error('IndexedDB get failed'))
  })
}

export async function cacheSet<T>(key: string, entry: CacheEntry<T>): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).put(entry, key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('IndexedDB set failed'))
  })
}

/** 清除全部缓存(数据管理页「清除缓存」按钮): 下次进入页面全量重拉 */
export async function cacheClear(): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).clear()
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('IndexedDB clear failed'))
  })
}

/** 缓存是否可用(版本匹配): 结构版本变更时视为无缓存, 全量重拉 */
export function cacheValid<T>(cached: CacheEntry<T> | null): cached is CacheEntry<T> {
  return !!cached && cached.schema === CACHE_SCHEMA
}

/** 增量合并: 增量行按 date 覆盖缓存同日期行, 返回升序 */
export function mergeByDate<T extends { date: string }>(cached: T[], inc: T[]): T[] {
  const map = new Map<string, T>()
  for (const x of cached) map.set(x.date, x)
  for (const x of inc) map.set(x.date, x)
  return [...map.values()].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
}

/** 截断到缓存安全截止日: 最近热区数据不入缓存(每次热拉) */
export function settledData<T extends { date: string }>(merged: T[], endDate: string): T[] {
  if (!endDate) return merged
  return merged.filter(x => x.date <= endDate)
}
