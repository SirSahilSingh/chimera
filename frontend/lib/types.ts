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
