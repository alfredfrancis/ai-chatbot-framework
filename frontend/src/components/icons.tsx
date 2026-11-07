import type { ReactNode } from "react";

function Svg({ children, size = 18, sw = 1.8 }: { children: ReactNode; size?: number; sw?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

/** The AI Chatbot Framework mark: a signal wave inside a ring (evolved from the original logo). */
export function BrandMark({ size = 24, live = false }: { size?: number; live?: boolean }) {
  return (
    <svg aria-hidden="true" className={`wave${live ? " live" : ""}`} width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="#4BE3B0" strokeWidth={1.7} strokeLinecap="round">
      <circle cx="12" cy="12" r="9.5" />
      <path d="M6 12.5c1 0 1.1-3 2.2-3s1.1 6 2.2 6 1.1-8 2.2-8 1.1 6 2.2 6 1.1-2 2.2-2" />
    </svg>
  );
}

export function Mark({ size = "md", live = false }: { size?: "md" | "lg"; live?: boolean }) {
  return <div className={`mark${size === "lg" ? " lg" : ""}`}><BrandMark size={size === "lg" ? 44 : 24} live={live} /></div>;
}

export function Lockup() {
  return (
    <>
      <Mark />
      <span className="words"><b>AI Chatbot</b><span>Framework</span></span>
    </>
  );
}

/** Animated "working" wave. */
export const WaveLine = () => (
  <svg aria-hidden="true" className="wave live" width="40" height="16" viewBox="0 0 40 16" fill="none"
    stroke="var(--signal-strong)" strokeWidth={1.8} strokeLinecap="round">
    <path d="M1 8c3 0 3-6 6-6s3 12 6 12 3-12 6-12 3 12 6 12 3-6 6-6 3 4 6 4" />
  </svg>
);

export const IconPlus = () => <Svg size={16} sw={2.2}><path d="M12 5v14M5 12h14" /></Svg>;
export const IconFolder = ({ size = 18 }: { size?: number }) => (
  <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="var(--signal-soft)" stroke="var(--signal-text)" strokeWidth={1.6}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </svg>
);
export const IconFile = () => <Svg sw={1.6}><path d="M6 3h9l4 4v14H6z" /><path d="M9 12h7M9 16h5" /></Svg>;
export const IconImage = () => <Svg sw={1.6}><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M4 16l5-5 4 4 3-3 4 4" /></Svg>;
export const IconClock = () => <Svg><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></Svg>;
export const IconPlug = () => <Svg><path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0zM12 16v5" /></Svg>;
export const IconSpark = () => <Svg><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /><path d="M19 17l.7 1.8 1.8.7-1.8.7L19 22l-.7-1.8-1.8-.7 1.8-.7z" /></Svg>;
export const IconDrawer = () => <Svg><path d="M4 5h16v14H4z" /><path d="M4 13h5l1 2h4l1-2h5" /></Svg>;
export const IconGear = () => (
  <Svg><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" /></Svg>
);
export const IconArrowUp = () => <Svg sw={2.2}><path d="M12 19V5M6 11l6-6 6 6" /></Svg>;
export const IconUpload = () => <Svg size={28}><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></Svg>;
export const IconCheck = () => <Svg size={14} sw={2.6}><path d="M5 12l5 5 9-10" /></Svg>;
export const IconX = () => <Svg size={14} sw={2.6}><path d="M6 6l12 12M18 6 6 18" /></Svg>;
export const IconMenu = () => <Svg><path d="M4 7h16M4 12h16M4 17h16" /></Svg>;
export const IconTrash = () => <Svg size={16}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></Svg>;
