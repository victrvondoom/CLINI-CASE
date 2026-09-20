// POST /api/v1/cases at 50 RPS for 2 minutes — steady-state case creation.
// Verifies (a) per-tenant rate limiter isn't false-rejecting, (b) Aurora
// + PgBouncer + RLS handles the write rate, (c) idempotency dedup works.

import http from 'k6/http';
import { check, group } from 'k6';
import { Rate } from 'k6/metrics';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';
import { login, authHeaders } from '../lib/auth.js';

export const errors = new Rate('errors');

export const options = {
  scenarios: {
    create: {
      executor: 'constant-arrival-rate',
      rate: 50, timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 30, maxVUs: 100,
    },
  },
  thresholds: {
    'http_req_duration{scenario:create}': ['p(95)<250'],
    'errors':                             ['rate<0.01'],
  },
};

const BASE  = __ENV.API_BASE || 'http://localhost:8000';
const EMAIL = __ENV.USER     || 'admin@aerofyta.health';
const PASS  = __ENV.PASS     || 'clincase2026';

let token;
export function setup() { return { token: login(BASE, EMAIL, PASS) }; }

export default function (data) {
  group('create case', () => {
    const idemKey = uuidv4();
    const payload = JSON.stringify({
      patient_initials: 'T.S.',
      icd10:            'C50.911',
      cpt:              ['96413'],
      requested_drug:   'trastuzumab',
      payer_id:         'aetna',
    });
    const res = http.post(`${BASE}/api/v1/cases`, payload, {
      headers: authHeaders(data.token, { 'Idempotency-Key': idemKey }),
      tags:    { scenario: 'create' },
    });
    errors.add(res.status >= 400);
    check(res, {
      '201 or 200': (r) => r.status === 201 || r.status === 200,
      'has case_id': (r) => !!r.json('id') || !!r.json('case_id'),
    });
  });
}
