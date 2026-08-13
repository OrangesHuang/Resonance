import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchDataStatus, fetchDataJobs, fetchScheduledTasks, startDataJob } from '../api/client'
import type { StartJobRequest } from '../api/types'

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
