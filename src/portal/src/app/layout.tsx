"use client";

import { useState } from "react";
import localFont from "next/font/local";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "@/hooks";
import "./globals.css";
// Theme entry point (docs/design/ui-contract.md): loads the installed design
// tokens so every var(--...) reference across the portal resolves. CAP-3 moved
// these tokens out of globals.css into design-system/ner-portal/tokens.css
// (merged with the ner-portal token contract brought in from main); this is
// the load that makes that file live again.
import "../../design-system/ner-portal/tokens.css";

// Self-hosted rather than `next/font/google`. That helper fetches from
// fonts.gstatic.com at build time, and the build container cannot resolve it — the same
// DNS gap that breaks `db-init`. Every request failed, retried three times, and Next
// fell back silently, so the shipped image rendered in fallback fonts. The files are
// fetched by `scripts/fetch-fonts.mjs` and committed; all three are OFL-licensed, which
// permits redistribution.
//
// Variable fonts, so one file covers the whole weight axis each family declares.
const hankenGrotesk = localFont({
  src: "../fonts/hanken-grotesk.woff2",
  variable: "--font-display",
  display: "swap",
  weight: "100 900",
});

const inter = localFont({
  src: "../fonts/inter.woff2",
  variable: "--font-body",
  display: "swap",
  weight: "100 900",
});

const jetbrainsMono = localFont({
  src: "../fonts/jetbrains-mono.woff2",
  variable: "--font-mono",
  display: "swap",
  weight: "100 800",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
          },
        },
      })
  );

  return (
    <html
      lang="en"
      className={`${hankenGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('portal-theme');if(t==='dark')document.documentElement.classList.add('dark');}catch(e){}})();`,
          }}
        />
      </head>
      <body>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <ToastProvider>{children}</ToastProvider>
          </AuthProvider>
        </QueryClientProvider>
      </body>
    </html>
  );
}
