import axios from 'axios';

// TEMPORARY: NEXT_PUBLIC_* vars are bundled into the client-side JS, so
// this key is visible to anyone who opens devtools on the admin dashboard.
// It's enough to unblock deployment today, but the correct fix is a
// Next.js API route that holds ADMIN_API_KEY server-side and proxies
// admin calls, so the key never reaches the browser. Do that before this
// dashboard is exposed to anyone beyond trusted admins.
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
    'X-Admin-Key': process.env.NEXT_PUBLIC_ADMIN_API_KEY || '',
  },
});

export default api;
