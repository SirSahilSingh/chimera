import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ children, size = 18, ...props }: IconProps & { children: React.ReactNode }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>;
}

export const GridIcon = (props: IconProps) => <Icon {...props}><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></Icon>;
export const ListIcon = (props: IconProps) => <Icon {...props}><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3 6h.01M3 12h.01M3 18h.01" strokeWidth="3" /></Icon>;
export const ShieldIcon = (props: IconProps) => <Icon {...props}><path d="M12 3 20 6v5c0 5-3.4 8.2-8 10-4.6-1.8-8-5-8-10V6l8-3Z" /><path d="m8.5 12 2.2 2.2 4.8-5" /></Icon>;
export const AuditIcon = (props: IconProps) => <Icon {...props}><path d="M5 4h14v16H5z" /><path d="M8 8h8M8 12h8M8 16h5" /></Icon>;
export const SearchIcon = (props: IconProps) => <Icon {...props}><circle cx="10.8" cy="10.8" r="6.3" /><path d="m16 16 4.5 4.5" /></Icon>;
export const ArrowUpRightIcon = (props: IconProps) => <Icon {...props}><path d="M7 17 17 7M8 7h9v9" /></Icon>;
export const ArrowRightIcon = (props: IconProps) => <Icon {...props}><path d="M5 12h14M13 6l6 6-6 6" /></Icon>;
export const ChevronDownIcon = (props: IconProps) => <Icon {...props}><path d="m6 9 6 6 6-6" /></Icon>;
export const CheckIcon = (props: IconProps) => <Icon {...props}><path d="m5 12 4.3 4.3L19 7" /></Icon>;
export const AlertIcon = (props: IconProps) => <Icon {...props}><path d="M12 3 22 20H2L12 3Z" /><path d="M12 9v5M12 17h.01" strokeWidth="2" /></Icon>;
export const AlertCircleIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" strokeWidth="2" /></Icon>;
export const ClockIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3 2" /></Icon>;
export const RefreshIcon = (props: IconProps) => <Icon {...props}><path d="M20 11a8 8 0 0 0-14.8-3L3 11" /><path d="M3 5v6h6M4 13a8 8 0 0 0 14.8 3L21 13" /><path d="M21 19v-6h-6" /></Icon>;
export const ExternalIcon = (props: IconProps) => <Icon {...props}><path d="M14 5h5v5M19 5l-8 8" /><path d="M18 13v5H5V6h5" /></Icon>;
export const XIcon = (props: IconProps) => <Icon {...props}><path d="m6 6 12 12M18 6 6 18" /></Icon>;
export const FlaskIcon = (props: IconProps) => <Icon {...props}><path d="M9 3h6M10 3v6l-5.5 9.3A1.8 1.8 0 0 0 6 21h12a1.8 1.8 0 0 0 1.5-2.7L14 9V3" /><path d="M7.3 16h9.4" /></Icon>;
export const ArrowLeftIcon = (props: IconProps) => <Icon {...props}><path d="M19 12H5M11 18l-6-6 6-6" /></Icon>;
export const SettingsIcon = (props: IconProps) => <Icon {...props}><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" /><path d="m19.4 15 .1.1a1.8 1.8 0 0 1-2.5 2.5l-.1-.1a1.8 1.8 0 0 0-3.1 1.3v.2a1.8 1.8 0 0 1-3.6 0v-.2a1.8 1.8 0 0 0-3.1-1.3l-.1.1a1.8 1.8 0 1 1-2.5-2.5l.1-.1A1.8 1.8 0 0 0 4.2 12a1.8 1.8 0 0 0-1.6-1.8h-.2a1.8 1.8 0 0 1 0-3.6h.2A1.8 1.8 0 0 0 4.2 3.5l-.1-.1a1.8 1.8 0 1 1 2.5-2.5l.1.1A1.8 1.8 0 0 0 9.8 0v-.2" transform="translate(0 4.5)" /></Icon>;
export const TuneIcon = (props: IconProps) => <Icon {...props}><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="2" fill="currentColor" stroke="none" /><circle cx="15" cy="17" r="2" fill="currentColor" stroke="none" /></Icon>;
export const CopyIcon = (props: IconProps) => <Icon {...props}><rect x="8" y="8" width="11" height="11" rx="1.5" /><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8" /></Icon>;
export const InfoIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="12" r="8.5" /><path d="M12 10.5v5M12 7.5h.01" strokeWidth="2" /></Icon>;
export const MicIcon = (props: IconProps) => <Icon {...props}><rect x="8.5" y="3" width="7" height="11" rx="3.5" /><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M8.5 21h7" /></Icon>;
export const MicOffIcon = (props: IconProps) => <Icon {...props}><path d="M8.5 8.5V6.5a3.5 3.5 0 0 1 6.7-1.5M15.5 10v4a3.5 3.5 0 0 1-6.1 2.4M5.5 11.5a6.5 6.5 0 0 0 11.2 4.5M12 18v3M8.5 21h7M4 4l16 16" /></Icon>;
export const PhoneCallIcon = (props: IconProps) => <Icon {...props}><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" /></Icon>;
export const ZapIcon = (props: IconProps) => <Icon {...props}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" fill="none" /></Icon>;
export const BarChartIcon = (props: IconProps) => <Icon {...props}><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></Icon>;
export const BrainIcon = (props: IconProps) => <Icon {...props}><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-5.04z" /><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-5.04z" /></Icon>;
export const ActivityIcon = (props: IconProps) => <Icon {...props}><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></Icon>;
export const CpuIcon = (props: IconProps) => <Icon {...props}><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" /><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" /></Icon>;
export const ServerIcon = (props: IconProps) => <Icon {...props}><rect x="2" y="2" width="20" height="8" rx="2" /><rect x="2" y="14" width="20" height="8" rx="2" /><line x1="6" y1="6" x2="6.01" y2="6" strokeWidth="2" /><line x1="6" y1="18" x2="6.01" y2="18" strokeWidth="2" /></Icon>;
export const SlidersIcon = (props: IconProps) => <Icon {...props}><line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" /><line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" /><line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" /><line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" /><line x1="17" y1="16" x2="23" y2="16" /></Icon>;
