import type { ReactNode } from "react";

function Svg({ children, size = 20 }: { children: ReactNode; size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

const WAVE = "4.4,12 6.3,15.8 8.2,8.4 10.1,15.8 12,8.4 13.9,15.8 15.8,8.4 17.7,15.8 19.6,12";

/** The AI Chatbot Framework logo mark: a green ring holding a three-peak wave. */
export function Mark({ size = 26, live = false }: { size?: number; live?: boolean }) {
  return (
    <span className="mark">
      <svg aria-hidden="true" className={live ? "wave-live" : undefined} width={size} height={size} viewBox="0 0 24 24"
        fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10.25" />
        <polyline points={WAVE} />
      </svg>
    </span>
  );
}

export function Lockup({ size = 26 }: { size?: number }) {
  return <><Mark size={size} /><span className="wordmark">AI Chatbot Framework</span></>;
}

export const IconPlus = ({ size = 18 }: { size?: number }) => <Svg size={size}><path d="M12 5v14M5 12h14" /></Svg>;
export const IconSearch = () => <Svg size={18}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Svg>;
export const IconChat = () => <Svg><path d="M4 5h16v11H9l-5 4z" /></Svg>;
export const IconDrawer = () => <Svg><path d="M4 5h16v14H4z" /><path d="M4 13h5l1 2h4l1-2h5" /></Svg>;
export const IconSpark = ({ size = 20 }: { size?: number }) => <Svg size={size}><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /></Svg>;
export const IconClock = () => <Svg><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></Svg>;
export const IconPlug = () => <Svg><path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0zM12 16v5" /></Svg>;
export const IconGear = () => <Svg size={18}><circle cx="12" cy="12" r="3" /><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" /></Svg>;
export const IconLogout = () => <Svg size={18}><path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" /></Svg>;
export const IconFolder = () => <svg aria-hidden="true" className="folder" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>;
export const IconFile = () => <Svg><path d="M6 3h9l4 4v14H6z" /><path d="M9 12h7M9 16h5" /></Svg>;
export const IconImage = () => <Svg><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M4 16l5-5 4 4 3-3 4 4" /></Svg>;
export const IconArrowUp = () => <Svg size={18}><path d="M12 19V5M6 11l6-6 6 6" /></Svg>;
export const IconUpload = () => <Svg size={28}><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></Svg>;
export const IconPaperclip = () => <Svg size={18}><path d="M20 11.5 12.2 19.3a5 5 0 0 1-7.1-7.1l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4L15 6.9" /></Svg>;
export const IconCheck = () => <Svg size={16}><path d="M5 12l5 5 9-10" /></Svg>;
export const IconX = () => <Svg size={16}><path d="M6 6l12 12M18 6 6 18" /></Svg>;
export const IconMenu = () => <Svg><path d="M4 7h16M4 12h16M4 17h16" /></Svg>;
export const IconTrash = () => <Svg size={18}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></Svg>;

export function Keys({ keys }: { keys: string[] }) {
  return <span className="keys">{keys.map((k) => <span key={k} className="kbd">{k}</span>)}</span>;
}
