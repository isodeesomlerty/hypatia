import { NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../../lib/apiBaseUrl";
import { getViewerRequestHeaders } from "../../../../lib/viewer";

export async function POST(request: Request) {
  try {
    const body = await request.text();
    const authHeaders = await getViewerRequestHeaders();
    const response = await fetch(`${getApiBaseUrl()}/v1/uploads/direct-batch`, {
      method: "POST",
      body,
      headers: {
        ...authHeaders,
        "content-type": "application/json",
      },
    });
    const responseText = await response.text();
    return new NextResponse(responseText, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (error) {
    const detail =
      error instanceof Error
        ? error.message
        : "Hypatia V2 could not reach the direct upload API.";
    return NextResponse.json({ detail }, { status: 502 });
  }
}
