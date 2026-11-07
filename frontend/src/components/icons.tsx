import type { ReactNode } from "react";

function Svg({ children, size = 18, sw = 1.8 }: { children: ReactNode; size?: number; sw?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

export const IconPlus = () => <Svg><path d="M12 5v14M5 12h14" /></Svg>;
export const IconChat = () => <Svg><path d="M4 5h16v11H9l-5 4z" /></Svg>;
export const IconClock = () => <Svg><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></Svg>;
export const IconPlug = () => <Svg><path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0zM12 16v5" /></Svg>;
export const IconDoc = () => <Svg><path d="M6 3h9l4 4v14H6z" /><path d="M9 12h7M9 16h5" /></Svg>;
export const IconGear = () => (
  <Svg><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" /></Svg>
);
export const IconArrowUp = () => <Svg sw={2.2}><path d="M12 19V5M6 11l6-6 6 6" /></Svg>;
export const IconCheck = () => <Svg size={14} sw={2.4}><path d="M5 12l5 5 9-10" /></Svg>;
export const IconX = () => <Svg size={14} sw={2.4}><path d="M6 6l12 12M18 6 6 18" /></Svg>;
export const IconMenu = () => <Svg><path d="M4 7h16M4 12h16M4 17h16" /></Svg>;
export const IconTrash = () => <Svg size={16}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></Svg>;
export const IconAnchor = () => (
  <Svg size={26} sw={2.2}><circle cx="12" cy="5" r="2" /><path d="M12 7v14M5 13a7 7 0 0 0 14 0M8 10h8" /></Svg>
);
