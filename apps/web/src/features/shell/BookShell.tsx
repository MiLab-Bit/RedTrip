import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  mode?: "spread" | "folio";
  className?: string;
};

/**
 * Open book with a dimensional shell.
 * The volume may lean in space; text inside stays upright.
 */
export function BookShell({ children, mode = "folio", className = "" }: Props) {
  return (
    <div className={["book-scene", className].filter(Boolean).join(" ")}>
      <div className="book-desk-glow" aria-hidden />
      <div className={`book-volume book-volume--${mode}`}>
        <div className="book-board" aria-hidden />
        <div className="book-edge book-edge-left" aria-hidden />
        <div className="book-edge book-edge-right" aria-hidden />
        <div className="book-edge book-edge-foot" aria-hidden />
        {mode === "folio" && <div className="book-folio-crease" aria-hidden />}
        <div className="book-block">
          <div className="book-block-inner">{children}</div>
        </div>
        <div className="book-curl" aria-hidden />
        <div className="book-ribbon" aria-hidden />
      </div>
    </div>
  );
}
