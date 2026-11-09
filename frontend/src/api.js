export const API = '/api/v1/'

async function request(path, options) {
  const response = await fetch(API + path, options)
  const type = response.headers.get('content-type') || ''
  const data = type.includes('application/json') ? await response.json() : null
  if (!response.ok) {
    const message = data?.detail || (data && Object.entries(data).map(([field, value]) => field + ': ' + value).join(' · '))
    const error = new Error(message || (response.status === 403 ? 'Access denied.' : 'Request failed (' + response.status + '). Check the backend server.'))
    error.status = response.status
    throw error
  }
  return data
}

export const get = path => request(path)

export async function save(path, payload, method = 'POST') {
  const {csrfToken} = await get('auth/csrf/')
  const multipart = payload instanceof FormData
  const headers = {'X-CSRFToken': csrfToken}
  if (!multipart) headers['Content-Type'] = 'application/json'
  return request(path, {
    method,
    headers,
    body: multipart ? payload : JSON.stringify(payload),
  })
}

