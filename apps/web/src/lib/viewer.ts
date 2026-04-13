import { headers } from "next/headers";
import { auth, currentUser } from "@clerk/nextjs/server";

import { buildDemoWorkspaceBundle } from "./demoWorkspace";
import type { ViewerSummary } from "./types";

export type ViewerRequestHeaders = Record<string, string>;

const clerkEnabled = Boolean(
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY,
);

function deriveDefaultWorkspaceId(userId: string) {
  const sanitized = userId.replace(/[^a-zA-Z0-9]/g, "");
  const suffix = sanitized.slice(-12).toLowerCase() || "personal";
  return `ws-${suffix}`;
}

export async function getViewerRequestHeaders(): Promise<ViewerRequestHeaders> {
  if (clerkEnabled) {
    const authState = await auth();
    if (authState.userId) {
      const user = await currentUser();
      const jwtTemplate = process.env.CLERK_JWT_TEMPLATE;
      const token = jwtTemplate
        ? await authState.getToken({ template: jwtTemplate })
        : await authState.getToken();
      if (!token) {
        throw new Error(
          "Clerk is enabled, but no API token is available. Configure CLERK_JWT_TEMPLATE for Hypatia V2.",
        );
      }
      const displayName =
        user?.fullName ||
        [user?.firstName, user?.lastName].filter(Boolean).join(" ") ||
        "Hypatia User";
      const email =
        user?.primaryEmailAddress?.emailAddress ||
        `${authState.userId}@clerk.local`;
      return {
        authorization: `Bearer ${token}`,
        "x-hypatia-user-id": authState.userId,
        "x-hypatia-user-email": email,
        "x-hypatia-user-name": displayName,
        "x-hypatia-auth-mode": "clerk",
        "x-hypatia-default-workspace-id": deriveDefaultWorkspaceId(authState.userId),
      };
    }
  }

  const incomingHeaders = await headers();
  const userId =
    incomingHeaders.get("x-hypatia-user-id") ||
    process.env.HYPATIA_DEV_USER_ID ||
    "demo-user";
  const email =
    incomingHeaders.get("x-hypatia-user-email") ||
    process.env.HYPATIA_DEV_USER_EMAIL ||
    "demo@hypatia.app";
  const displayName =
    incomingHeaders.get("x-hypatia-user-name") ||
    process.env.HYPATIA_DEV_USER_NAME ||
    "Hypatia Demo User";
  const authMode =
    incomingHeaders.get("x-hypatia-auth-mode") ||
    process.env.HYPATIA_AUTH_MODE ||
    "development";
  const defaultWorkspaceId =
    incomingHeaders.get("x-hypatia-default-workspace-id") ||
    process.env.HYPATIA_DEFAULT_WORKSPACE_ID ||
    "demo";

  return {
    "x-hypatia-user-id": userId,
    "x-hypatia-user-email": email,
    "x-hypatia-user-name": displayName,
    "x-hypatia-auth-mode": authMode,
    "x-hypatia-default-workspace-id": defaultWorkspaceId,
  };
}

export function buildDemoViewer(): ViewerSummary {
  const bundle = buildDemoWorkspaceBundle("demo");
  return {
    user_id: "demo-user",
    email: "demo@hypatia.app",
    display_name: "Hypatia Demo User",
    auth_mode: "development",
    default_workspace_id: "demo",
    workspaces: [
      {
        workspace_id: bundle.summary.workspace_id,
        name: bundle.summary.name,
        role: "owner",
      },
      {
        workspace_id: "cognitive-lab",
        name: "Cognitive Influence Lab",
        role: "member",
      },
    ],
  };
}
