import "./globals.css";
import { Shell } from "../components/shell";

export const metadata = {
  title: "CHIMERA · Revenue recovery intelligence",
  description: "Autonomous revenue recovery operations for observable payment failures.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{/* THESIS: make the recovery agent's work visible from detection through outcome; refuse the generic KPI dashboard. OWN-WORLD: near-black incident board, phosphor mint signals, amber intervention marks, thin technical rules, stacked control-room modules. STORY: the operator sees revenue at risk, follows the observed pattern, understands the stored decision, and can act only through backend authority. FIRST VIEWPORT: command headline, risk readout, four meaningful KPIs, active-problem flow, failure patterns, and live recovery activity. FORM: incident-response control room, assigned surface direction 6, seed a89c15cf / direction seed 12894e05. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md */}<Shell>{children}</Shell></body></html>;
}
