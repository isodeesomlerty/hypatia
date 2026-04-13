"use client";

import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/nextjs";

type AuthControlsProps = {
  compact?: boolean;
};

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

export function AuthControls({ compact = false }: AuthControlsProps) {
  if (!clerkEnabled) {
    return (
      <div className={`auth-controls${compact ? " auth-controls--compact" : ""}`}>
        <span className="auth-chip">Development auth</span>
      </div>
    );
  }

  return (
    <div className={`auth-controls${compact ? " auth-controls--compact" : ""}`}>
      <SignedOut>
        <SignInButton mode="modal">
          <button type="button" className="secondary-link">
            Sign in
          </button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button type="button" className="primary-link">
            Create account
          </button>
        </SignUpButton>
      </SignedOut>
      <SignedIn>
        <div className="auth-chip auth-chip--active">Authenticated workspace</div>
        <UserButton afterSignOutUrl="/" />
      </SignedIn>
    </div>
  );
}
