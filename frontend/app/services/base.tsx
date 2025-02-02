const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';
export const API_BASE_URL = `${baseUrl.replace(/\/+$/, '')}/admin/`;