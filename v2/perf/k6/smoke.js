import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 40 },
    { duration: "60s", target: 100 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.005"],
    http_req_duration: ["p(95)<100", "p(99)<250"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8081";
const TOKEN = __ENV.ACCESS_TOKEN || "";

function headers() {
  const h = { "Content-Type": "application/json" };
  if (TOKEN) h["Authorization"] = `Bearer ${TOKEN}`;
  return h;
}

export default function () {
  const reqHeaders = { headers: headers() };

  const live = http.get(`${BASE_URL}/live`);
  check(live, { "live is 200": (r) => r.status === 200 });

  const ready = http.get(`${BASE_URL}/ready`);
  check(ready, { "ready is 200": (r) => r.status === 200 });

  if (TOKEN) {
    const routes = [
      "/api/v2/analytics/overview",
      "/api/v2/stations?limit=25",
      "/api/v2/users?limit=25",
      "/api/v2/tickets?limit=25",
      "/api/v2/swaps?limit=25",
      "/api/v2/inventory/summary",
      "/api/v2/inventory/low-stock",
      "/api/v2/admin/health",
    ];

    for (const path of routes) {
      const res = http.get(`${BASE_URL}${path}`, reqHeaders);
      check(res, { [`${path} status < 500`]: (r) => r.status < 500 });
    }
  }

  sleep(1);
}
