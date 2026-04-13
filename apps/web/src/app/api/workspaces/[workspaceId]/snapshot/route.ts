import { NextResponse } from "next/server";

import { getWorkspaceSnapshot } from "../../../../../lib/api";
import { getViewerRequestHeaders } from "../../../../../lib/viewer";

type RouteContext = {
  params: Promise<{ workspaceId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  try {
    const { workspaceId } = await context.params;
    const authHeaders = await getViewerRequestHeaders();
    const url = new URL(request.url);
    const paperId = url.searchParams.get("paper");
    const relationshipId = url.searchParams.get("relationship");

    const snapshot = await getWorkspaceSnapshot(workspaceId, authHeaders, {
      paperId,
      relationshipId,
    });
    return NextResponse.json(snapshot);
  } catch (error) {
    const detail =
      error instanceof Error
        ? error.message
        : "Hypatia V2 could not refresh the workspace snapshot.";
    return NextResponse.json({ detail }, { status: 502 });
  }
}
