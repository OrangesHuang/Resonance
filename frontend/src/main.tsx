import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './styles/global.css'

const queryClient = new QueryClient({
  defaultOptions: {
    // 指数退避重试: 后端刚启动未就绪时页面自动恢复, 而不是直接显示失败
    queries: {
      retry: 3,
      retryDelay: attempt => Math.min(500 * 2 ** attempt, 5000),
      staleTime: 15000,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
