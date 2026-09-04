export type CaseStatus =
  | "NEW"
  | "DECIDED"
  | "ACTION_PENDING"
  | "ACTION_EXECUTED"
  | "PROMISE_TO_PAY_PENDING"
  | "RECOVERED"
  | "UNRECOVERED"
  | "CLOSED";

export type Candidate = {
  action: string;
  status: string;
  blocked_reason: string | null;
  predicted_probability: number;
  recoverable_amount_paise: number;
  expected_gross_recovery_paise: number;
  action_cost_paise: number;
  incentive_cost_paise: number;
  fatigue_penalty_paise: number;
  expected_net_value_paise: number;
  expected_net_without_action_cost_paise: number;
  expected_net_without_fatigue_paise: number;
  rank: number | null;
  friction_rank: number;
  fatigue_reason: string;
};

export type Decision = {
  id: string;
  recovery_case_id: string;
  decision_run_id: string;
  selected_action: string;
  predicted_probability: number;
  expected_gross_recovery_paise: number;
  expected_net_value_paise: number;
  model_version: string;
  feature_schema_version: string;
  engine_version: string;
  simulator_version: string | null;
  prompt_version: string | null;
  decision_timestamp: string;
  created_at: string;
  candidates: Candidate[];
  trace_json: Record<string, unknown>;
};

export type Execution = {
  id: string;
  recovery_case_id: string;
  decision_id: string;
  action: string;
  provider_mode: "LOCAL" | "MOCK" | "TEST" | "LIVE" | string;
  status: string;
  idempotency_key: string;
  provider_reference: string | null;
  error_code: string | null;
  error_message: string | null;
  response_json: Record<string, string>;
  executed_at: string | null;
  created_at: string;
};

export type StructuredExplanation = {
  summary: string;
  recommendation: { action: string; reason: string };
  key_factors: { factor: string; impact: string }[];
  alternatives: { action: string; reason_not_selected: string }[];
  next_step: string;
  operator_note: string;
  limitations: string[];
};

export type Explanation = {
  id: string;
  decision_id: string;
  recovery_case_id: string;
  explanation_source: "llm" | "fallback";
  provider: string;
  model_name: string;
  prompt_version: string;
  explanation_version: string;
  input_context_hash: string;
  output_hash: string;
  generated_at: string;
  fallback_reason: string | null;
  structured_explanation: StructuredExplanation;
};

export type RecoveryCase = {
  id: string;
  external_event_id: string;
  payment_id: string;
  customer_id: string;
  customer_phone: string | null;
  amount_paise: number;
  currency: string;
  failure_reason: string;
  incident_flag: boolean;
  payment_method: string;
  decision_timestamp: string;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  latest_decision: Decision | null;
  latest_execution: Execution | null;
  audit_count: number;
};

export type PaginatedCases = {
  items: RecoveryCase[];
  page: number;
  page_size: number;
  total: number;
};

export type ProviderMode = "LOCAL" | "MOCK" | "TEST" | "LIVE" | string;

export type ScheduledRetry = {
  id: string;
  recovery_case_id: string;
  intervention_id: string;
  decision_id: string;
  idempotency_key: string;
  attempt_number: number;
  scheduled_at: string;
  schedule_reason: string;
  eligibility_status: string;
  execution_status: string;
  provider_mode: ProviderMode;
  executed_at: string | null;
  created_at: string;
};

export type EscalationEvent = {
  id: string;
  escalation_id: string;
  event_type: string;
  status: string;
  actor: string;
  payload_json: Record<string, unknown>;
  sequence_number: number;
  created_at: string;
};

export type Escalation = {
  id: string;
  recovery_case_id: string;
  intervention_id: string;
  decision_id: string;
  escalation_reason: string;
  context_json: Record<string, unknown>;
  priority: number;
  idempotency_key: string;
  status: string;
  provider_mode: ProviderMode;
  created_at: string;
  updated_at: string;
  events: EscalationEvent[];
};

export type JourneyEvent = {
  id: string;
  event_type: string;
  source: string;
  timestamp: string | null;
  provider_mode: ProviderMode | null;
  payload: Record<string, unknown>;
};

export type JourneyCandidate = Pick<Candidate, "action" | "status" | "predicted_probability" | "expected_net_value_paise" | "rank">;

export type JourneyDecision = {
  id: string;
  selected_action: string;
  predicted_probability: number;
  expected_gross_recovery_paise: number;
  expected_net_value_paise: number;
  model_version: string;
  feature_schema_version: string;
  engine_version: string;
  simulator_version: string | null;
  decision_timestamp: string;
  created_at: string;
  trace_json: Record<string, unknown>;
  candidates: JourneyCandidate[];
};

export type JourneyIntervention = {
  id: string;
  decision_id: string;
  action: string;
  status: string;
  priority: number;
  created_at: string;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  executions: JourneyExecution[];
  outcomes: JourneyOutcome[];
  events: JourneyEvent[];
};

export type JourneyExecution = {
  id: string;
  action: string | null;
  provider_mode: ProviderMode;
  status: string;
  provider_reference: string | null;
  error_code: string | null;
  executed_at: string | null;
  created_at: string;
  response_json: Record<string, unknown>;
};

export type JourneyOutcome = {
  id: string;
  status: string;
  recovered_amount_paise: number | null;
  occurred_at: string;
  source: string;
};

export type JourneyPayment = {
  id: string;
  provider: string;
  provider_mode: ProviderMode;
  status: string;
  amount_paise: number;
  short_url: string;
  created_at: string;
  events: JourneyEvent[];
};

export type PaymentOrder = {
  id: string;
  provider: string;
  provider_mode: ProviderMode;
  provider_order_id: string;
  checkout_key_id: string | null;
  external_reference_id: string;
  customer_id: string;
  customer_phone: string | null;
  customer_email: string | null;
  amount_paise: number;
  currency: string;
  description: string;
  status: string;
  provider_payment_id: string | null;
  failure_reason: string | null;
  recovery_case_id: string | null;
  idempotency_key: string;
  request_hash: string;
  result_hash: string;
  created_at: string;
  updated_at: string;
};

export type JourneyInitialOrder = {
  id: string;
  provider: string;
  provider_mode: ProviderMode;
  provider_order_id: string;
  amount_paise: number;
  currency: string;
  status: string;
  provider_payment_id: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
  events: JourneyEvent[];
};

export type JourneyMessage = {
  id: string;
  provider: string;
  provider_mode: ProviderMode;
  status: string;
  delivery_state: string;
  provider_message_id: string | null;
  failure_reason: string | null;
  failure_code: string | null;
  created_at: string;
  events: JourneyEvent[];
};

export type JourneyRetry = {
  id: string;
  action: string;
  provider: string;
  provider_mode: ProviderMode;
  status: string;
  provider_reference: string | null;
  validated_result_json: Record<string, unknown>;
  created_at: string;
};

export type JourneyScheduledRetry = {
  id: string;
  provider_mode: ProviderMode;
  scheduled_at: string;
  execution_status: string;
  eligibility_status: string;
  executed_at: string | null;
  created_at: string;
};

export type JourneyVoiceCall = {
  id: string;
  intervention_id: string;
  provider: string;
  provider_mode: ProviderMode;
  status: string;
  scenario: string;
  provider_call_reference: string | null;
  outcome_intent: string | null;
  payment_link?: string | null;
  failure_reason: string | null;
  failure_code: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  turns: { id: string; speaker: string; text: string; intent: string | null; timestamp: string }[];
  events: JourneyEvent[];
};

export type JourneyEscalation = {
  id: string;
  status: string;
  reason: string;
  priority: number;
  provider_mode: ProviderMode;
  created_at: string;
  events: JourneyEvent[];
};

export type RecoveryJourney = {
  case: { id: string; external_event_id: string; payment_id: string; customer_id: string; customer_phone: string | null; amount_paise: number; currency: string; failure_reason: string; incident_flag: boolean; payment_method: string; decision_timestamp: string; status: string; created_at: string; updated_at: string };
  decision: JourneyDecision | null;
  latest_explanation: Explanation | null;
  interventions: JourneyIntervention[];
  execution: JourneyExecution[];
  payments: JourneyPayment[];
  initial_orders: JourneyInitialOrder[];
  messages: JourneyMessage[];
  retries: JourneyRetry[];
  scheduled_retries: JourneyScheduledRetry[];
  voice_calls: JourneyVoiceCall[];
  escalations: JourneyEscalation[];
  audit_trail: JourneyEvent[];
};

export type DemoRecoveryResponse = {
  case_id: string;
  decision_id: string;
  intervention_id: string;
  selected_action: string;
  status: string;
  provider: string | null;
  provider_mode: ProviderMode | null;
  journey_url: string;
};

export type DemoRunResponse = {
  scenario: "payment_recovery" | "technical_retry" | "voice_recovery" | "escalation";
  case_id: string;
  decision_id: string;
  intervention_id: string;
  selected_action: string;
  current_status: string;
  provider: string | null;
  provider_mode: ProviderMode;
  provider_mode_label: string;
  journey_url: string;
};

export type LearningActionMetric = {
  action: string;
  selection_count: number;
  selection_rate: number | null;
  completed_count: number;
  recovery_rate: number | null;
  gross_recovered_value_paise: number;
  net_recovered_value_paise: number;
  average_predicted_probability: number | null;
  average_expected_net_value_paise: number | null;
  average_intervention_cost_paise: number | null;
  average_fatigue_penalty_paise: number | null;
  reliability: string;
};

export type LearningOverview = {
  analysis_version: string;
  provider_mode_filter: string | null;
  provider_modes: string[];
  sample_size: number;
  data_warning: string | null;
  overall: { total_cases: number; completed_cases: number; recovered_cases: number; unrecovered_cases: number; pending_cases: number; recovery_rate: number | null; gross_recovered_amount_paise: number; net_recovered_amount_paise: number; average_recovered_value_paise: number | null; average_time_to_outcome_seconds: number | null };
  actions: LearningActionMetric[];
  failures: { failure_reason: string; case_count: number; completed_count: number; recovery_rate: number | null; best_action: string | null; best_action_recovery_rate: number | null; recovered_value_paise: number; selected_action_distribution: Record<string, number> }[];
  calibration: { status: string; sample_size: number; average_predicted: number | null; observed_recovery_rate: number | null; calibration_gap: number | null; brier_score: number | null; reliability_buckets: { bucket: string; sample_size: number; average_predicted: number; observed_recovery_rate: number; reliability: string }[] };
  insights: { category: string; severity: string; title: string; evidence: string; sample_size: number; reliability: string; limitation: string }[];
  recommendations: { category: string; recommendation: string; evidence: string; sample_size: number; limitation: string; review_requirement: string }[];
};

export type LearningFunnel = { stage: string; entered: number; completed: number; not_applicable: number; drop_off_rate: number | null; status: string }[];
export type LearningProvider = { provider: string; provider_mode: string; attempt_count: number; successful_requests: number; failed_requests: number; timeout_count: number; retry_count: number; duplicate_suppression_count: number; average_latency_seconds: number | null; final_recovery_count: number; reliability: string };
export type LearningDrift = { status: string; baseline_sample_size?: number; current_sample_size?: number; metrics: { metric: string; drift_score: number; severity: string; baseline_sample_size: number; current_sample_size: number; baseline_distribution?: Record<string, number>; current_distribution?: Record<string, number>; baseline_value?: number; current_value?: number }[] };

export type ProviderReadiness = { provider_name: string; provider_type: string; implementation: string; provider_mode: string; readiness_status: string; last_verification_timestamp: string | null; last_verification_result: string; last_error_type: string | null; capabilities: string[]; limitations: string[]; verification_id: string | null; latency_ms: number | null; idempotency_status: string | null };
export type ProviderVerificationResponse = ProviderReadiness & { operation: string; verification_result: string; error_type: string | null; message: string; input_hash: string; output_hash: string; verification_record: Record<string, unknown> | null };
export type SystemHealth = { status: string; database: string; model_compatibility: string; api_environment: string };
export type ArenaStrategySummary = { strategy: string; policy_name: string; recovered_revenue_paise: number; net_value_paise: number; interventions: number; policy_violations: number; recovery_rate: number; bar_percent: number };
export type ArenaResponse = { batch: { label: string; total_events: number; value_at_risk_paise: number; seeds: number[]; count_per_seed: number }; rows: ArenaStrategySummary[]; methodology: string; same_event_batch_across_policies: boolean; simulator_version: string; config_hash: string };

export type RecoveryIntelligence = {
  case_id: string;
  detection: {
    problem_type: "payment_failure";
    failure_reason: string;
    payment_method: string;
    incident_detected: boolean;
    failure_timestamp: string;
    amount_at_risk_paise: number;
    contact_window_status: string;
    outbound_contact_eligible: boolean;
    current_recovery_state: string;
    severity: "low" | "medium" | "high";
    observable_history: Record<string, number | null>;
    summary: string;
  };
  diagnosis: {
    primary_cause: string;
    confidence: "low" | "medium" | "high";
    contributing_factors: string[];
    evidence: { field: string; value: string; interpretation: string }[];
    alternatives: { category: string; explanation: string }[];
    statement: string;
  };
  decision: {
    selected_action: string;
    decision_summary: string;
    alternatives: { action: string; status: string; predicted_probability: number; expected_net_value_paise: number; reason_not_selected: string }[];
    constraints: { action: string; reason: string }[];
    cost_affected: boolean;
    fatigue_affected: boolean;
    constraint_affected: boolean;
    highest_probability_action: string | null;
    highest_probability_action_differed: boolean;
  } | null;
  intervention: {
    action: string | null;
    status: string;
    provider_mode: string;
    execution_summary: string;
    voice: { label: string; status: string; provider_mode: string; customer_intent: string | null; conversation_result: string; payment_link_requested: boolean; final_intervention_state: string } | null;
  };
  outcome: {
    status: string;
    recovered_amount_paise: number | null;
    outcome_timestamp: string | null;
    time_to_outcome_seconds: number | null;
    summary: string;
    recovery_path: string[];
  };
  journey_summary: { stages_completed: string[]; current_stage: string; timeline: { event_type: string; label: string; timestamp: string | null; source: string }[] };
  explanation: { explanation_source: string; provider: string; model_name: string; generated_at: string; fallback_reason: string | null; summary: string } | null;
  insights: { type: string; message: string }[];
};

export type VoiceTurn = {
  id: string;
  speaker: string;
  text: string;
  intent: string | null;
  confidence?: number;
  timestamp: string;
};

export type VoiceHistoryResponse = {
  call: JourneyVoiceCall;
  turns: VoiceTurn[];
  events: JourneyEvent[];
};
