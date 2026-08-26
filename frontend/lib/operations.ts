import type { CaseStatus, RecoveryCase } from "./types";

export function isRecovered(item: RecoveryCase) {
  return item.status === "RECOVERED";
}

export function isClosed(item: RecoveryCase) {
  return item.status === "CLOSED";
}

export function isUnresolved(item: RecoveryCase) {
  return !isRecovered(item) && !isClosed(item) && item.status !== "UNRECOVERED";
}

export function isActiveRecovery(item: RecoveryCase) {
  return ["DECIDED", "ACTION_PENDING", "ACTION_EXECUTED", "PROMISE_TO_PAY_PENDING"].includes(item.status);
}

export function statusLabel(status: CaseStatus | string) {
  const labels: Record<string, string> = {
    NEW: "Detected",
    DECIDED: "Diagnosed",
    ACTION_PENDING: "Intervening",
    ACTION_EXECUTED: "Intervening",
    PROMISE_TO_PAY_PENDING: "Promise pending",
    RECOVERED: "Recovered",
    UNRECOVERED: "Unresolved",
    CLOSED: "Closed",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export function caseDisplayId(item: RecoveryCase) {
  return item.external_event_id || item.id;
}
