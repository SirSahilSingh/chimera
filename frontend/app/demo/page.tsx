"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { ArrowRightIcon } from "../../components/icons";
import { IntelligenceTitle } from "../../components/intelligence-workspace";
import paymentLinkImg from "../../payment link.jpg";
import voiceRecoveryImg from "../../vocie recovery.svg";

export default function DemoScenariosPage() {
  const router = useRouter();

  return (
    <div className="evaluation-page demo-scenarios-page">
      <IntelligenceTitle title="Demo Scenarios" />

      <div className="demo-cards-grid">
        {/* Payment Recovery Card */}
        <div
          className="demo-image-card"
          role="button"
          tabIndex={0}
          onClick={() => router.push("/checkout")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") router.push("/checkout");
          }}
        >
          <div className="demo-image-wrapper">
            <Image
              src={paymentLinkImg}
              alt="Payment Recovery"
              className="demo-card-image"
              priority
            />
          </div>
          <div className="demo-card-content">
            <div className="demo-card-title-row">
              <h2 className="demo-card-heading">Payment Recovery</h2>
              <span className="demo-card-arrow"><ArrowRightIcon size={16} /></span>
            </div>
            <p className="demo-card-subheading">Razorpay TEST payment failure recovery</p>
          </div>
        </div>

        {/* Voice-Assisted Recovery Card */}
        <div
          className="demo-image-card"
          role="button"
          tabIndex={0}
          onClick={() => router.push("/voice-recovery")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") router.push("/voice-recovery");
          }}
        >
          <div className="demo-image-wrapper">
            <Image
              src={voiceRecoveryImg}
              alt="Voice-Assisted Recovery"
              className="demo-card-image"
              priority
            />
          </div>
          <div className="demo-card-content">
            <div className="demo-card-title-row">
              <h2 className="demo-card-heading">Voice-Assisted Recovery</h2>
              <span className="demo-card-arrow"><ArrowRightIcon size={16} /></span>
            </div>
            <p className="demo-card-subheading">Live Hinglish outbound phone call recovery</p>
          </div>
        </div>
      </div>
    </div>
  );
}
