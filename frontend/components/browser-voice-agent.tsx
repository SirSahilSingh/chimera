"use client";

import { VobizVoiceAgent } from "./vobiz-voice-agent";

export { VobizVoiceAgent };

export function BrowserVoiceAgent({
  interventionId,
  amountPaise,
  failureReason,
  paymentMethod,
  initialPhone,
}: {
  interventionId: string;
  amountPaise: number;
  failureReason: string;
  paymentMethod: string;
  initialPhone?: string | null;
}) {
  return (
    <VobizVoiceAgent
      interventionId={interventionId}
      amountPaise={amountPaise}
      failureReason={failureReason}
      paymentMethod={paymentMethod}
      initialPhone={initialPhone}
    />
  );
}
