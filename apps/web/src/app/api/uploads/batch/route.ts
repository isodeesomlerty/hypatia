import { NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../../lib/apiBaseUrl";
import { getViewerRequestHeaders } from "../../../../lib/viewer";

export async function POST(request: Request) {
  try {
    const authHeaders = await getViewerRequestHeaders();
    const contentType = request.headers.get("content-type") ?? "";
    let response: Response;

    if (contentType.includes("application/json")) {
      const body = await request.text();
      response = await fetch(`${getApiBaseUrl()}/v1/uploads/batch`, {
        method: "POST",
        body,
        headers: {
          ...authHeaders,
          "content-type": "application/json",
        },
      });
    } else {
      const formData = await request.formData();
      response = await fetch(`${getApiBaseUrl()}/v1/uploads/batch-files`, {
        method: "POST",
        body: formData,
        headers: authHeaders,
      });
    }

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
        : "Hypatia V2 could not reach the upload API.";
    return NextResponse.json({ detail }, { status: 502 });
  }
}
