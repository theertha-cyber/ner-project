"use client";

import { useState, useEffect, useRef, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

/* ─── Animated background — isolated so form re-renders don't reset RAF transforms */
function AnimatedBackground() {
  const orb1 = useRef<HTMLDivElement>(null);
  const orb2 = useRef<HTMLDivElement>(null);
  const orb3 = useRef<HTMLDivElement>(null);
  const orb4 = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const target  = { x: 0.5, y: 0.5 };
    const current = { x: 0.5, y: 0.5 };
    const t0 = Date.now();
    let raf: number;

    const onMove = (e: MouseEvent) => {
      target.x = e.clientX / window.innerWidth;
      target.y = e.clientY / window.innerHeight;
    };

    const tick = () => {
      /* faster lerp = snappier follow */
      current.x += (target.x - current.x) * 0.14;
      current.y += (target.y - current.y) * 0.14;

      const t  = (Date.now() - t0) / 1000;
      const dx = (current.x - 0.5) * 240;   /* wider parallax range */
      const dy = (current.y - 0.5) * 200;

      orb1.current && (orb1.current.style.transform =
        `translate(${dx * 1.2  + Math.sin(t * 0.28) * 24}px,${dy * 1.2  + Math.cos(t * 0.38) * 18}px)`);
      orb2.current && (orb2.current.style.transform =
        `translate(${-dx * 0.7 + Math.cos(t * 0.22) * 30}px,${-dy * 0.7 + Math.sin(t * 0.32) * 24}px)`);
      orb3.current && (orb3.current.style.transform =
        `translate(${dx * 0.5  + Math.sin(t * 0.18 + 1) * 34}px,${dy * 0.5  + Math.cos(t * 0.28 + 1) * 24}px)`);
      orb4.current && (orb4.current.style.transform =
        `translate(${-dx * 0.9 + Math.cos(t * 0.15) * 20}px,${-dy * 0.9 + Math.sin(t * 0.25) * 16}px)`);

      raf = requestAnimationFrame(tick);
    };

    window.addEventListener("mousemove", onMove);
    raf = requestAnimationFrame(tick);
    return () => { window.removeEventListener("mousemove", onMove); cancelAnimationFrame(raf); };
  }, []);

  return (
    <div aria-hidden style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none" }}>
      <div ref={orb1} style={{ position: "absolute", width: "72vw", height: "72vw", left: "-18vw", top: "-28vw", borderRadius: "50%", filter: "blur(78px)", opacity: 0.92, background: "radial-gradient(circle at 30% 30%, #c2410c, #ea580c 38%, transparent 65%)", willChange: "transform" }} />
      <div ref={orb2} style={{ position: "absolute", width: "50vw", height: "50vw", right: "-8vw", top: "12vh", borderRadius: "50%", filter: "blur(90px)", opacity: 0.55, background: "radial-gradient(circle at 50% 50%, #334155, transparent 62%)", willChange: "transform" }} />
      <div ref={orb3} style={{ position: "absolute", width: "44vw", height: "44vw", left: "24vw", bottom: "-14vw", borderRadius: "50%", filter: "blur(80px)", opacity: 0.5, background: "radial-gradient(circle at 50% 50%, #f59e0b, transparent 62%)", willChange: "transform" }} />
      <div ref={orb4} style={{ position: "absolute", width: "36vw", height: "36vw", right: "12vw", top: "-8vh", borderRadius: "50%", filter: "blur(72px)", opacity: 0.75, background: "radial-gradient(circle at 50% 50%, #c2410c, #9a3412 42%, transparent 66%)", willChange: "transform" }} />
    </div>
  );
}

/* ─── Eye icon SVGs */
const EyeOpen = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
);

const EyeOff = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
);

/* ─── Demo chips */
const DEMO_CHIPS = [
  { role: "system_admin",  label: "system_admin",  sub: "admin@ner-platform.dev", email: "admin@ner-platform.dev",   password: "Admin123!" },
  { role: "tenant_admin",  label: "tenant_admin",  sub: "admin@acme.dev",          email: "tenant_admin@acme.dev",    password: "Admin123!" },
  { role: "annotator",     label: "annotator",     sub: "annotator@acme.dev",      email: "annotator@acme.dev",       password: "Admin123!" },
  { role: "business_user", label: "business_user", sub: "business@acme.dev",       email: "business@acme.dev",        password: "Admin123!" },
];

/* text-shadow presets — layered for depth without being stark */
const TS_SM = "0 1px 6px rgba(0,0,0,0.45), 0 0 28px rgba(0,0,0,0.2)";
const TS_H1 = "0 2px 10px rgba(0,0,0,0.5), 0 0 40px rgba(0,0,0,0.22)";

/* ─── Login page */
export default function LoginPage() {
  const [email, setEmail]           = useState("");
  const [password, setPassword]     = useState("");
  const [showPassword, setShowPw]   = useState(false);
  const [error, setError]           = useState("");
  const [isPending, setIsPending]   = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const { login, user } = useAuth();
  const router  = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const skipAutoNavRef = useRef(false);

  useEffect(() => {
    if (user !== null && !skipAutoNavRef.current) router.replace("/dashboard");
  }, [user, router]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setIsPending(true);
    try {
      await login(email, password);
      skipAutoNavRef.current = true;
      setIsTransitioning(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsPending(false);
    }
  };

  const fillDemo = (chip: (typeof DEMO_CHIPS)[0]) => {
    setEmail(chip.email);
    setPassword(chip.password);
    setTimeout(() => formRef.current?.requestSubmit(), 0);
  };

  const isDemo = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

  return (
    <div style={{ position: "relative", minHeight: "100vh", overflow: "hidden", display: "flex", alignItems: "center", background: "var(--color-surface-page)" }}>
      <AnimatedBackground />

      <div style={{ position: "relative", zIndex: 1, width: "100%", maxWidth: 1200, margin: "0 auto", padding: "40px 60px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 60 }}>

        {/* ── Left: hero copy ── */}
        <div style={{ flex: "1 1 0", color: "#fff", maxWidth: 520 }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 64 }}>
            <div style={{ width: 34, height: 34, borderRadius: 9, background: "#fff", display: "grid", placeItems: "center", fontFamily: "var(--font-display,'Hanken Grotesk',sans-serif)", fontWeight: 800, color: "#c2410c", fontSize: 19, flexShrink: 0 }}>n</div>
            <span style={{ fontFamily: "var(--font-display,'Hanken Grotesk',sans-serif)", fontWeight: 700, fontSize: 18, letterSpacing: "-0.02em", textShadow: TS_SM }}>nerp</span>
          </div>

          <div style={{ fontFamily: "var(--font-mono,'JetBrains Mono',monospace)", fontSize: 12, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 20, textShadow: TS_SM }}>
            Multi-tenant document intelligence
          </div>
          <h1 style={{ fontFamily: "var(--font-display,'Hanken Grotesk',sans-serif)", fontWeight: 800, fontSize: "clamp(32px,4vw,56px)", lineHeight: 1.02, letterSpacing: "-0.035em", margin: "0 0 22px", textShadow: TS_H1 }}>
            Define your entities.<br />
            Train your model.<br />
            Extract the truth.
          </h1>
        </div>

        {/* ── Right: floating card ── */}
        <div style={{ flexShrink: 0, width: 380, background: "rgba(255,255,255,0.72)", backdropFilter: "blur(28px) saturate(1.5)", WebkitBackdropFilter: "blur(28px) saturate(1.5)", border: "1px solid rgba(255,255,255,0.8)", borderRadius: 22, padding: "36px 32px", boxShadow: "0 32px 80px -20px rgba(15,23,42,0.4),0 0 0 1px rgba(255,255,255,0.5)", animation: "popIn 0.45s ease both" }}>

          <h2 style={{ fontFamily: "var(--font-display,'Hanken Grotesk',sans-serif)", fontWeight: 700, fontSize: 24, letterSpacing: "-0.025em", margin: "0 0 4px", color: "#0f172a" }}>Sign in</h2>
          <p style={{ margin: "0 0 22px", fontSize: 13.5, color: "#475569" }}>Welcome back.<br />Authenticate to your tenant console.</p>

          <form ref={formRef} onSubmit={handleSubmit}>
            <label htmlFor="email" style={{ display: "block", fontSize: 11.5, fontWeight: 600, color: "#475569", marginBottom: 6, fontFamily: "var(--font-mono,'JetBrains Mono',monospace)", letterSpacing: "0.04em", textTransform: "uppercase" }}>Email</label>
            <input
              id="email" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)}
              onFocus={(e) => { e.target.style.borderColor = "#c2410c"; e.target.style.boxShadow = "0 0 0 3px rgba(194,65,12,0.12)"; }}
              onBlur={(e)  => { e.target.style.borderColor = "#e2e8f0"; e.target.style.boxShadow = "none"; }}
              style={{ width: "100%", padding: "11px 13px", borderRadius: 11, border: "1.5px solid #e2e8f0", background: "rgba(255,255,255,0.9)", color: "#0f172a", fontFamily: "var(--font-mono,'JetBrains Mono',monospace)", fontSize: 13.5, marginBottom: 15, outline: "none", boxSizing: "border-box", transition: "border-color 0.15s,box-shadow 0.15s" }}
            />

            <label htmlFor="password" style={{ display: "block", fontSize: 11.5, fontWeight: 600, color: "#475569", marginBottom: 6, fontFamily: "var(--font-mono,'JetBrains Mono',monospace)", letterSpacing: "0.04em", textTransform: "uppercase" }}>Password</label>
            {/* password wrapper — position:relative so the eye button can sit inside */}
            <div style={{ position: "relative", marginBottom: error ? 12 : 20 }}>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={(e) => { e.target.style.borderColor = "#c2410c"; e.target.style.boxShadow = "0 0 0 3px rgba(194,65,12,0.12)"; }}
                onBlur={(e)  => { e.target.style.borderColor = "#e2e8f0"; e.target.style.boxShadow = "none"; }}
                style={{ width: "100%", padding: "11px 42px 11px 13px", borderRadius: 11, border: "1.5px solid #e2e8f0", background: "rgba(255,255,255,0.9)", color: "#0f172a", fontFamily: "var(--font-mono,'JetBrains Mono',monospace)", fontSize: 13.5, outline: "none", boxSizing: "border-box", transition: "border-color 0.15s,box-shadow 0.15s" }}
              />
              <button
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPw((v) => !v)}
                style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", padding: 2, cursor: "pointer", color: "#94a3b8", display: "flex", alignItems: "center" }}
              >
                {showPassword ? <EyeOff /> : <EyeOpen />}
              </button>
            </div>

            {error && <p role="alert" style={{ fontSize: 13, color: "#dc2626", margin: "0 0 14px" }}>{error}</p>}

            <button type="submit" disabled={isPending} style={{ width: "100%", padding: "12px 0", border: "none", borderRadius: 11, background: "#c2410c", color: "#fff", fontFamily: "var(--font-display,'Hanken Grotesk',sans-serif)", fontWeight: 700, fontSize: 15, cursor: isPending ? "not-allowed" : "pointer", opacity: isPending ? 0.65 : 1, boxShadow: "0 8px 20px -8px rgba(194,65,12,0.7)", transition: "opacity 0.15s", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              {isPending && <span data-testid="spinner" style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.35)", borderTopColor: "#fff", borderRadius: "50%", display: "inline-block", animation: "spin 0.7s linear infinite" }} />}
              {isPending ? "Signing in…" : "Sign in →"}
            </button>
          </form>

          {isDemo && (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "22px 0 14px" }}>
                <div style={{ flex: 1, height: 1, background: "#e2e8f0" }} />
                <span style={{ fontSize: 10.5, color: "#475569", fontFamily: "var(--font-mono,'JetBrains Mono',monospace)", letterSpacing: "0.09em", whiteSpace: "nowrap" }}>DEMO · SIGN IN AS</span>
                <div style={{ flex: 1, height: 1, background: "#e2e8f0" }} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {DEMO_CHIPS.map((chip) => (
                  <button key={chip.role} type="button" aria-label={chip.label} onClick={() => fillDemo(chip)}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = "#c2410c"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = "#e2e8f0"; }}
                    style={{ display: "flex", flexDirection: "column", gap: 2, alignItems: "flex-start", padding: "9px 11px", borderRadius: 11, border: "1.5px solid #e2e8f0", background: "rgba(255,255,255,0.8)", cursor: "pointer", textAlign: "left", transition: "border-color 0.15s" }}>
                    <span style={{ fontFamily: "var(--font-display,'Hanken Grotesk',sans-serif)", fontWeight: 700, fontSize: 13, color: "#0f172a" }}>{chip.label}</span>
                    <span style={{ fontFamily: "var(--font-mono,'JetBrains Mono',monospace)", fontSize: 10, color: "#475569" }}>{chip.sub}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {isTransitioning && (
        <div
          data-testid="transition-overlay"
          style={{ position: "fixed", inset: 0, zIndex: 50, background: "radial-gradient(circle at 30% 40%, #f59e0b, #ea580c 40%, #c2410c 70%)", animation: "orbBurst 0.55s ease-in both" }}
          onAnimationEnd={() => router.replace("/dashboard")}
        />
      )}

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
