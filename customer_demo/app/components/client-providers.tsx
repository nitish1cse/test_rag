"use client";

import React from "react";
import { SessionProvider } from "next-auth/react";
import { Providers } from "../providers";

export function ClientProviders({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <Providers>
        {children}
      </Providers>
    </SessionProvider>
  );
} 