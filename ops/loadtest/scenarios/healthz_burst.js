// /api/v1/healthz/deep at 1000 RPS for 30 seconds.
// This is the simplest scenario — should always be cheap. If it isn't,
// some upstream layer (WAF, ALB, Linkerd) is the bottleneck.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

export const errors = new Rate('errors');
export const latency = new Trend('healthz_latency_ms', true);

export const options = {
  scenarios: {
    healthz: {
      executor: 'constant-arrival-rate',
      rate: 1000, timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 50, maxVUs: 200,
    },
  },
  thresholds: {
    'http_req_duration{scenario:healthz}': ['p(95)<50'],
    'errors':                              ['rate<0.001'],
  },
};

const BASE = __ENV.API_BASE || 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE}/api/v1/healthz/deep`);
  errors.add(res.status !== 200);
  latency.add(res.timings.duration);
  check(res, { '200': (r) => r.status === 200 });
}
