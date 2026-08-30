import "./globals.css";
import { Shell } from "../components/shell";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";

export const metadata = {
  title: "CHIMERA · Revenue recovery intelligence",
  description: "Autonomous revenue recovery operations for observable payment failures.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}><body>{/* THESIS: make the recovery agent's work visible from detection through outcome; refuse the generic KPI dashboard. OWN-WORLD: pitch-black operations workspace, white Geist typography, quiet borders, and sparse execution rows. STORY: the operator sees exposure, active work, and provider evidence immediately, then opens the relevant case journey. FIRST VIEWPORT: compact shell, one operational feature card, three summary readouts, attention queue, pipeline, and recent cases. FORM: Vercel-inspired control-plane dashboard, clean hierarchy, no eyebrow text or decorative subheads. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md */}<Shell>{children}</Shell></body></html>;
}
