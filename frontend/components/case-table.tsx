import Link from "next/link";
import { useRouter } from "next/navigation";
import { ExternalIcon } from "./icons";
import { formatAction, formatDate, formatFailureReason, formatPaise, formatTime } from "../lib/formatters";
import { caseDisplayId, isRecovered } from "../lib/operations";
import type { RecoveryCase } from "../lib/types";
import { StatusBadge } from "./shell";

export function CaseTable({ cases, compact = false, queueMode = false }: { cases: RecoveryCase[]; compact?: boolean; queueMode?: boolean }) {
  const router = useRouter();
  const openCase = (id: string) => router.push(`/cases/${id}`);
  return <div className={`table-frame operational-table ${compact ? "compact-table" : ""}`}><table className="data-table queue-table"><thead><tr><th>Case</th><th>Failure Signal</th><th>Value at Risk</th><th>Stored Action</th><th>Lifecycle</th><th>Time</th></tr></thead><tbody>{cases.map((item) => <tr key={item.id} tabIndex={0} role="link" onClick={() => openCase(item.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openCase(item.id); } }}>
    <td><Link className="case-link" href={`/cases/${item.id}`}><strong>{caseDisplayId(item)}</strong><span className="cell-sub">{item.customer_id} · {item.payment_id}</span></Link></td>
    <td><span className="reason-label">{formatFailureReason(item.failure_reason)}</span></td>
    <td className="money-cell">{formatPaise(item.amount_paise, item.currency)}</td>
    <td>{item.latest_decision ? <span className="action-cell"><span className="action-dot" />{formatAction(item.latest_decision.selected_action)}</span> : <span className="muted-text">Awaiting decision</span>}</td>
    <td><StatusBadge status={item.status} /></td>
    <td><Link className={`next-action ${queueMode && item.status === "DECIDED" ? "emphasis" : ""}`} href={`/cases/${item.id}`}><strong>{formatDate(item.updated_at)}</strong><span>{formatTime(item.updated_at)}</span></Link></td>
  </tr>)}</tbody></table>{cases.length === 0 && <div className="empty-state"><div className="empty-mark"><ExternalIcon size={18} /></div><h3>No cases match this view</h3><p>Change the filters or wait for the next stored payment failure.</p></div>}</div>;
}

function nextAction(item: RecoveryCase) {
  if (item.status === "NEW") return "Review case";
  if (item.status === "DECIDED") return "Execute stored action";
  if (item.status === "ACTION_PENDING") return "Authorize intervention";
  if (item.status === "ACTION_EXECUTED" || item.status === "PROMISE_TO_PAY_PENDING") return "Monitor outcome";
  if (item.status === "UNRECOVERED") return "Investigate outcome";
  if (isRecovered(item)) return "View recovered outcome";
  return "Open Decision Room";
}
