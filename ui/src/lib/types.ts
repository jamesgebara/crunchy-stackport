export interface ServiceStats {
  status: string
  resources: Record<string, number>
}

export interface StatsResponse {
  services: Record<string, ServiceStats>
  total_resources: number
  uptime_seconds: number
}
