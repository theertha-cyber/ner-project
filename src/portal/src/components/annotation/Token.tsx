"use client";

export type TokenHighlight =
  | { kind: "confirmed"; color: string }
  | { kind: "suggested"; color: string }
  | { kind: "none" };

interface TokenProps {
  token: string;
  highlight: TokenHighlight;
  onClick: () => void;
}

export function Token({ token, highlight, onClick }: TokenProps) {
  let style: React.CSSProperties = {
    display: "inline-block",
    padding: "2px 1px",
    margin: "2px 2px",
    borderRadius: 3,
    cursor: "pointer",
    fontSize: 14,
    lineHeight: "1.6",
    fontFamily: "var(--font-body, Inter, sans-serif)",
    color: "var(--color-text-primary)",
    userSelect: "none",
    transition: "background 0.1s",
  };

  if (highlight.kind === "confirmed") {
    style = {
      ...style,
      background: highlight.color + "33",
      borderBottom: `2px solid ${highlight.color}`,
      color: "var(--color-text-primary)",
    };
  } else if (highlight.kind === "suggested") {
    style = {
      ...style,
      background: highlight.color + "18",
      border: `1px dashed ${highlight.color}`,
      borderRadius: 3,
    };
  }

  return (
    <span style={style} onClick={onClick}>
      {token}
    </span>
  );
}
