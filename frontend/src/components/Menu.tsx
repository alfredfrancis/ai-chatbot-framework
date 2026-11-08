import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { IconMore } from "./icons";

export type MenuItem = {
  label: string;
  onSelect: () => void | Promise<void>;
  icon?: ReactNode;
  /** Destructive: drawn in red, and the first choice asks again with this label before running. */
  confirm?: string;
  /** Shown only on phones (the action has its own button on wider screens). */
  phoneOnly?: boolean;
};

const visible = (el: HTMLElement | null) =>
  [...(el?.querySelectorAll<HTMLButtonElement>("[role=menuitem]") ?? [])].filter((b) => b.offsetParent !== null);

/** A ⋯ button with a short list of actions: a popover on wide screens, a bottom sheet on phones. */
export function MoreMenu({ label, items, className = "" }: { label: string; items: MenuItem[]; className?: string }) {
  const [open, setOpen] = useState(false);
  const [asking, setAsking] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const id = useId();

  const close = () => { setOpen(false); setAsking(null); };
  useEffect(() => {
    if (!open) return;
    visible(list.current)[0]?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    const onDown = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) close(); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, [open]);

  const choose = async (item: MenuItem) => {
    if (item.confirm && asking !== item.label) { setAsking(item.label); return; }
    close();
    await item.onSelect();
  };
  const move = (e: ReactKeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const shown = visible(list.current);
    const at = shown.indexOf(document.activeElement as HTMLButtonElement);
    shown[(at + (e.key === "ArrowDown" ? 1 : shown.length - 1)) % shown.length]?.focus();
  };

  return (
    <div className={`menu ${className}`} ref={box}>
      <button type="button" className={`btn ghost icon${open ? " on" : ""}`} aria-label={label} title={label}
        aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined} onClick={() => (open ? close() : setOpen(true))}>
        <IconMore />
      </button>
      {open && (
        <>
          <div className="menu-scrim" aria-hidden="true" onClick={close} />
          <div className="menu-pop" role="menu" id={id} aria-label={label} ref={list} onKeyDown={move}>
            <span className="grip" aria-hidden="true" />
            {items.map((item) => {
              const confirming = asking === item.label;
              return (
                <button key={item.label} type="button" role="menuitem"
                  className={`menu-item${item.confirm ? " danger" : ""}${item.phoneOnly ? " phone-only" : ""}${confirming ? " confirming" : ""}`}
                  onClick={() => choose(item)}>
                  {item.icon}{confirming ? item.confirm : item.label}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
