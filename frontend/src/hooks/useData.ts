import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchDataStatus, fetchDataJobs, fetchDataSettings, fetchScheduledTasks, startDataJob, updateDataSettings } from '../api/client'
import type { DataSettings, StartJobRequest } from '../api/types'

export function useScheduledTasks() {
  return useQuery({
    queryKey: ['data', 'scheduled'],
    queryFn: fetchScheduledTasks,
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
  })
}

export function useDataStatus(poll: boolean) {
  return useQuery({
    queryKey: ['data', 'status'],
    queryFn: fetchDataStatus,
    refetchInterval: poll ? 1500 : false,
    refetchIntervalInBackground: false,
  })
}

export function useDataJobs(poll: boolean) {
  return useQuery({
    queryKey: ['data', 'jobs'],
    queryFn: fetchDataJobs,
    refetchInterval: poll ? 1000 : false,
    refetchIntervalInBackground: false,
  })
}

export function useStartJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: StartJobRequest) => startDataJob(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data'] })
    },
  })
}

export function useDataSettings() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['data', 'settings'],
    queryFn: fetchDataSettings,
  })
  const update = useMutation({
    mutationFn: (body: DataSettings) => updateDataSettings(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data', 'status'] })
      queryClient.invalidateQueries({ queryKey: ['data', 'settings'] })
    },
  })
  return { query, update }
}
