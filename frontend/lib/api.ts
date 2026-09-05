import type { ArenaResponse, Decision, DemoRecoveryResponse, DemoRunResponse, Escalation, Explanation, LearningDrift, LearningFunnel, LearningOverview, LearningProvider, PaginatedCases, JourneyPayment, PaymentOrder, ProviderReadiness, ProviderVerificationResponse, RecoveryCase, Execution, RecoveryIntelligence, RecoveryJourney, ScheduledRetry, SystemHealth, JourneyVoiceCall, VoiceHistoryResponse } from "./types";

// Prefer the same-origin Next.js proxy locally so the browser does not need a
// separate CORS policy. An explicit public base remains available for a
// separately hosted API that already has the appropriate CORS configuration.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";
// Next rewrites proxy HTTP requests, but a browser WebSocket should connect
// directly to the FastAPI server. Set this when the API is not on localhost.
const API_WS_BASE = process.env.NEXT_PUBLIC_API_WS_BASE_URL ?? (
  API_BASE.startsWith("http") ? API_BASE : "http://localhost:8000/api/v1"
);

export function pipecatVoiceUrl(interventionId: string): string {
  const path = `${API_WS_BASE.replace(/\/$/, "")}/voice/pipecat/${encodeURIComponent(interventionId)}`;
  const url = new URL(path, typeof window === "undefined" ? "http://localhost" : window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

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
  startManualCall: (caseId: string) => request<JourneyVoiceCall>(`/recovery-cases/${caseId}/voice/call`, { method: "POST" }),
  reconcilePayment: (paymentId: string) => request<JourneyPayment>(`/payments/${paymentId}/reconcile`, { method: "POST" }),
  createPaymentOrder: (payload: { external_reference_id: string; customer_id: string; amount_paise: number; currency: "INR"; description: string; customer_phone?: string; customer_email?: string }) => request<PaymentOrder>("/payments/orders", { method: "POST", body: JSON.stringify(payload) }),
  getPaymentOrder: (orderId: string) => request<PaymentOrder>(`/payments/orders/${orderId}`),
  getIntelligence: (caseId: string) => request<RecoveryIntelligence>(`/recovery-cases/${caseId}/intelligence`),
  runRecoveryDemo: (payload: { external_event_id: string; payment_id: string; customer_id: string; amount_paise: number; currency: "INR"; failure_reason: string; incident_flag: boolean; payment_method: "card" | "upi" | "netbanking"; decision_timestamp: string }) => request<DemoRecoveryResponse>("/demo/recovery", { method: "POST", body: JSON.stringify(payload) }),
  runDemo: (payload: { scenario: DemoRunResponse["scenario"]; provider_mode: "LOCAL"; customer_phone?: string; amount_paise?: number; failure_reason?: string; payment_method?: "card" | "upi" | "netbanking" }) => request<DemoRunResponse>("/demo/run", { method: "POST", body: JSON.stringify(payload) }),
  learningOverview: (providerMode?: string) => request<LearningOverview>(`/learning/overview${providerMode ? `?provider_mode=${encodeURIComponent(providerMode)}` : ""}`),
  learningFunnel: (providerMode?: string) => request<{ funnel: { stages: LearningFunnel; largest_bottleneck: LearningFunnel[number] | null } }>(`/learning/funnel${providerMode ? `?provider_mode=${encodeURIComponent(providerMode)}` : ""}`),
  learningProviders: (providerMode?: string) => request<{ providers: LearningProvider[] }>(`/learning/providers${providerMode ? `?provider_mode=${encodeURIComponent(providerMode)}` : ""}`),
  learningDrift: (providerMode?: string) => request<LearningDrift>(`/learning/drift${providerMode ? `?provider_mode=${encodeURIComponent(providerMode)}` : ""}`),
  providerReadiness: () => request<ProviderReadiness[]>("/providers"),
  verifyProvider: (providerName: string) => request<ProviderVerificationResponse>(`/providers/${encodeURIComponent(providerName)}/verify`, { method: "POST", body: JSON.stringify({}) }),
  systemHealth: () => request<SystemHealth>("/health"),
  listEscalations: () => request<Escalation[]>("/escalations"),
  acknowledgeEscalation: (escalationId: string) => request<Escalation>(`/escalations/${encodeURIComponent(escalationId)}/acknowledge`, { method: "POST" }),
  resolveEscalation: (escalationId: string) => request<Escalation>(`/escalations/${encodeURIComponent(escalationId)}/resolve`, { method: "POST" }),
  listScheduledRetries: () => request<ScheduledRetry[]>("/retries/scheduled"),
  executeScheduledRetry: (retryId: string, force = true) => request<Execution>(`/retries/${encodeURIComponent(retryId)}/execute${force ? "?force=true" : ""}`, { method: "POST" }),
  runArena: (payload: { seeds?: number[]; count_per_seed?: number } = {}) => request<ArenaResponse>("/arena/run", { method: "POST", body: JSON.stringify({ seeds: payload.seeds ?? [400000], count_per_seed: payload.count_per_seed ?? 25 }) }),
  startOutboundCall: (payload: { intervention_id: string; customer_phone?: string }) =>
    request<JourneyVoiceCall>("/voice/outbound/call", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getVoiceHistory: (interventionId: string) =>
    request<VoiceHistoryResponse>(`/interventions/${encodeURIComponent(interventionId)}/voice/history`),
  pipecatVoiceUrl,
};
