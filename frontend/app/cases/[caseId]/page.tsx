"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "../../../lib/api";
import type { RecoveryCase } from "../../../lib/types";
import { DecisionRoom } from "../../../components/decision-room";
import { ErrorState, LoadingState } from "../../../components/shell";

export default function CasePage() {
  const params = useParams<{ caseId: string }>();
  const [caseData, setCaseData] = useState<RecoveryCase | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (!params.caseId) return; api.getCase(params.caseId).then(setCaseData).catch((err) => setError(err instanceof ApiError ? err.detail : "Case could not be loaded.")); }, [params.caseId]);
  if (error) return <ErrorState message={error} />;
  if (!caseData) return <LoadingState label="Loading decision room" />;
  return <DecisionRoom initialCase={caseData} />;
}
