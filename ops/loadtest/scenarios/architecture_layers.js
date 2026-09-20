// GET /api/v1/architecture/layers under load.
// This is the live architecture descriptor. It's read by judges, customers,
// and the frontend. Must be fast even under load.

import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';
import { login, authHeaders } from '../lib/auth.js';

export const errors = new Rate('errors');

export const options = {
  scenarios: {
    layers: {
      executor: 'ramping-arrival-rate',
      startRate: 5, timeUnit: '1s',
      preAllocatedVUs: 30,
      maxVUs: 100,
      stages: [
        { target: 50, duration: '30s' },
        { target: 50, duration: '30s' },
        { target: 0,  duration: '5s'  },
      ],
    },
  },
  thresholds: {
    'http_req_duration{scenario:layers}': ['p(95)<200'],
    'errors':                              ['rate<0.005'],
  },
};

const BASE  = __ENV.API_BASE || 'http://localhost:8000';
const EMAIL = __ENV.USER     || 'admin@aerofyta.health';
const PASS  = __ENV.PASS     || 'clincase2026';

export function setup() { return { token: login(BASE, EMAIL, PASS) }; }

export default function (data) {
  const res = http.get(`${BASE}/api/v1/architecture/layers`, {
    headers: authHeaders(data.token),
    tags: { scenario: 'layers' },
  });
  errors.add(res.status !== 200);
  check(res, {
    '200': (r) => r.status === 200,
    'has layers': (r) => Array.isArray(r.json('layers')),
    'has 6 layers': (r) => (r.json('layers') || []).length === 6,
  });
}
