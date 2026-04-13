"use client";

import { ClerkProvider } from "@clerk/nextjs";

type AppProvidersProps = {
  children: React.ReactNode;
};

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

export function AppProviders({ children }: AppProvidersProps) {
  if (!clerkEnabled) {
    return <>{children}</>;
  }

  return <ClerkProvider>{children}</ClerkProvider>;
}
