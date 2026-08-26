import Link from "next/link";
import { ArrowUpRightIcon, ExternalIcon } from "./icons";
import { formatAction, formatFailureReason, formatPaise } from "../lib/formatters";
import { caseDisplayId, isRecovered, statusLabel } from "../lib/operations";
import type { RecoveryCase } from "../lib/types";
import { StatusBadge } from "./shell";

export function CaseTable({ cases, compact = false }: { cases: RecoveryCase[]; compact?: boolean }) {
  return <div className={`table-frame operational-table ${compact ? "compact-table" : ""}`}><table className="data-table"><thead><tr><th>Case</th><th>Failure / diagnosis</th><th>Revenue at risk</th><th>CHIMERA action</th><th>Status</th><th>Outcome</th><th /></tr></thead><tbody>{cases.map((item) => <tr key={item.id}>
    <td><Link className="case-link" href={`/cases/${item.id}`}><strong>{caseDisplayId(item)}</strong><span className="cell-sub">{item.customer_id} · {item.payment_id}</span></Link></td>
    <td><span className="reason-label">{formatFailureReason(item.failure_reason)}</span><span className="diagnosis-sub">{item.incident_flag ? "Incident signal" : "Observed pattern"}</span></td>
    <td className="money-cell">{formatPaise(item.amount_paise, item.currency)}</td>
    <td>{item.latest_decision ? <span className="action-cell"><span className="action-dot" />{formatAction(item.latest_decision.selected_action)}</span> : <span className="muted-text">Awaiting decision</span>}</td>
    <td><StatusBadge status={item.status} /><span className="stage-sub">{statusLabel(item.status)}</span></td>
    <td>{isRecovered(item) ? <span className="outcome-value">{formatPaise(item.amount_paise, item.currency)}</span> : <span className="muted-text">{item.status === "UNRECOVERED" ? "Unresolved" : "Pending"}</span>}</td>
    <td><Link href={`/cases/${item.id}`} className="icon-link" aria-label={`Open ${caseDisplayId(item)}`}><ArrowUpRightIcon size={16} /></Link></td>
  </tr>)}</tbody></table>{cases.length === 0 && <div className="empty-state"><div className="empty-mark"><ExternalIcon size={18} /></div><h3>No recovery cases match</h3><p>Try changing the filters or create a new case through the API.</p></div>}</div>;
}
