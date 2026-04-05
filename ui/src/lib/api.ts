const API_BASE = '/api'

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/stats`)
  return res.json()
}

export async function fetchResources(service: string, type?: string) {
  const params = type ? `?type=${type}` : ''
  const res = await fetch(`${API_BASE}/resources/${service}${params}`)
  return res.json()
}

export async function fetchResourceDetail(service: string, type: string, id: string) {
  const res = await fetch(`${API_BASE}/resources/${service}/${type}/${encodeURIComponent(id)}`)
  return res.json()
}

export async function fetchS3Buckets() {
  const res = await fetch(`${API_BASE}/s3/buckets`)
  return res.json()
}

export async function fetchS3Bucket(bucket: string) {
  const res = await fetch(`${API_BASE}/s3/buckets/${encodeURIComponent(bucket)}`)
  return res.json()
}

export async function fetchS3Objects(bucket: string, prefix = '', delimiter = '/') {
  const params = new URLSearchParams({ prefix, delimiter })
  const res = await fetch(`${API_BASE}/s3/buckets/${encodeURIComponent(bucket)}/objects?${params}`)
  return res.json()
}

export async function fetchS3Object(bucket: string, key: string) {
  const res = await fetch(`${API_BASE}/s3/buckets/${encodeURIComponent(bucket)}/objects/${key}`)
  return res.json()
}

export function getS3DownloadUrl(bucket: string, key: string): string {
  return `${API_BASE}/s3/buckets/${encodeURIComponent(bucket)}/objects/${key}?download=1`
}
