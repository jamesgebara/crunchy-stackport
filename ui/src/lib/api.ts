import type { StatsResponse, ResourceListResponse, ResourceDetailResponse, S3Bucket, S3ObjectsResponse, S3ObjectDetail } from './types'

const API_BASE = '/api'

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`)
  return res.json()
}

export async function fetchStats(): Promise<StatsResponse> {
  return fetchJSON<StatsResponse>(`${API_BASE}/stats`)
}

export async function fetchResources(service: string, type?: string): Promise<ResourceListResponse> {
  const params = type ? `?type=${type}` : ''
  return fetchJSON<ResourceListResponse>(`${API_BASE}/resources/${service}${params}`)
}

export async function fetchResourceDetail(service: string, type: string, id: string): Promise<ResourceDetailResponse> {
  return fetchJSON<ResourceDetailResponse>(`${API_BASE}/resources/${service}/${type}/${encodeURIComponent(id)}`)
}

export async function fetchS3Buckets(): Promise<{ buckets: S3Bucket[] }> {
  return fetchJSON<{ buckets: S3Bucket[] }>(`${API_BASE}/s3/buckets`)
}

export async function fetchS3Bucket(bucket: string) {
  return fetchJSON(`${API_BASE}/s3/buckets/${encodeURIComponent(bucket)}`)
}

export async function fetchS3Objects(bucket: string, prefix = '', delimiter = '/'): Promise<S3ObjectsResponse> {
  const params = new URLSearchParams({ prefix, delimiter })
  return fetchJSON<S3ObjectsResponse>(`${API_BASE}/s3/buckets/${encodeURIComponent(bucket)}/objects?${params}`)
}

export async function fetchS3Object(bucket: string, key: string): Promise<S3ObjectDetail> {
  return fetchJSON<S3ObjectDetail>(`${API_BASE}/s3/buckets/${encodeURIComponent(bucket)}/objects/${key}`)
}

export function getS3DownloadUrl(bucket: string, key: string): string {
  return `${API_BASE}/s3/buckets/${encodeURIComponent(bucket)}/objects/${key}?download=1`
}
