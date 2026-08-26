import type { Decision, DemoRecoveryResponse, Explanation, PaginatedCases, RecoveryCase, Execution, RecoveryIntelligence, RecoveryJourney } from "./types";

// Prefer the same-origin Next.js proxy locally so the browser does not need a
// separate CORS policy. An explicit public base remains available for a
// separately hosted API that already has the appropriate CORS configuration.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Backend unavailable. Check the API service and try again.");
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : "The backend rejected this request.";
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

export const api = {
  listCases: (params: { page?: number; pageSize?: number; status?: string } = {}) => {
    const query = new URLSearchParams({ page: String(params.page ?? 1), page_size: String(params.pageSize ?? 50) });
    if (params.status) query.set("status", params.status);
    return request<PaginatedCases>(`/recovery-cases?${query.toString()}`);
  },
  getCase: (caseId: string) => request<RecoveryCase>(`/recovery-cases/${caseId}`),
  decide: (caseId: string) => request<Decision>(`/recovery-cases/${caseId}/decide`, { method: "POST" }),
  execute: (caseId: string) => request<Execution>(`/recovery-cases/${caseId}/execute`, { method: "POST" }),
  getDecision: (decisionId: string) => request<Decision>(`/decisions/${decisionId}`),
  explain: (decisionId: string) => request<Explanation>(`/decisions/${decisionId}/explain`, { method: "POST" }),
  getLatestExplanation: (decisionId: string) => request<Explanation>(`/decisions/${decisionId}/explanation`),
  getExplanationHistory: (decisionId: string) => request<Explanation[]>(`/decisions/${decisionId}/explanations`),
  getJourney: (caseId: string) => request<RecoveryJourney>(`/recovery-cases/${caseId}/journey`),
  getIntelligence: (caseId: string) => request<RecoveryIntelligence>(`/recovery-cases/${caseId}/intelligence`),
  runRecoveryDemo: (payload: { external_event_id: string; payment_id: string; customer_id: string; amount_paise: number; currency: "INR"; failure_reason: string; incident_flag: boolean; payment_method: "card" | "upi" | "netbanking"; decision_timestamp: string }) => request<DemoRecoveryResponse>("/demo/recovery", { method: "POST", body: JSON.stringify(payload) }),
};
