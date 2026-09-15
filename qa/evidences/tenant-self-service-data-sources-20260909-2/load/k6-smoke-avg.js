import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 1 },
    { duration: '60s', target: 5 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<10000'],
  },
};

const BASE = 'http://localhost:8000';

export default function () {
  let r = http.get(BASE + '/health');
  check(r, { 'health 200': (x) => x.status === 200 });
  const h = { Authorization: 'Bearer ' + __ENV.K6_TOKEN };
  r = http.get(BASE + '/api/v1/data-sources', { headers: h });
  check(r, {
    'list 200': (x) => x.status === 200,
    'safe shape': (x) => String(x.body || '').indexOf('connection_string') === -1,
  });
}
