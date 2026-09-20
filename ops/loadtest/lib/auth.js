// Shared auth helper for k6 scenarios — logs in once per VU, caches the token.
import http from 'k6/http';
import { check } from 'k6';

export function login(base, email, password) {
  const res = http.post(`${base}/api/v1/auth/login`, JSON.stringify({
    email, password
  }), { headers: { 'Content-Type': 'application/json' } });
  check(res, {
    'login 200': (r) => r.status === 200,
    'login has token': (r) => r.json('access_token') !== '',
  });
  return res.json('access_token');
}

export function authHeaders(token, extra = {}) {
  return Object.assign({
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  }, extra);
}
