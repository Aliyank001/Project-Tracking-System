import {defineConfig} from 'vite'

// Keep the browser host so Django's CSRF origin matches proxied POST requests.
const django = {target: 'http://127.0.0.1:8000', changeOrigin: false}
const proxy = {'/api': django, '/admin': django, '/static/admin': django}
export default defineConfig({server: {proxy}, preview: {proxy}})
