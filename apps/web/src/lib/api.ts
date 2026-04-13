import { buildDemoMeta, buildDemoWorkspaceBundle } from "./demoWorkspace";
import type {
  APIMetaResponse,
  ViewerSummary,
  WorkspaceBatchListResponse,
  WorkspaceBundle,
  WorkspaceGraphResponse,
  WorkspaceJobListResponse,
  WorkspacePaperListResponse,
  WorkspaceSummary,
} from "./types";
import { buildDemoViewer, type ViewerRequestHeaders } from "./viewer";

function getApiBaseUrl() {
  return (
    process.env.HYPATIA_API_BASE_URL ||
    process.env.NEXT_PUBLIC_HYPATIA_API_BASE_URL ||
    "http://127.0.0.1:8000"
  );
}

function demoFallbackEnabled() {
  return process.env.HYPATIA_ENABLE_DEMO_FALLBACK === "1";
}

async function fetchJSON<T>(
  path: string,
  authHeaders: ViewerRequestHeaders,
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
    headers: authHeaders,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export async function getWorkspaceBundle(
  workspaceId: string,
  authHeaders: ViewerRequestHeaders,
): Promise<WorkspaceBundle> {
  try {
    const [meta, viewer, summary, graph, papers, jobs, batches] = await Promise.all([
      fetchJSON<APIMetaResponse>("/v1/meta", authHeaders),
      fetchJSON<ViewerSummary>("/v1/viewer", authHeaders),
      fetchJSON<WorkspaceSummary>(`/v1/workspaces/${workspaceId}`, authHeaders),
      fetchJSON<WorkspaceGraphResponse>(
        `/v1/workspaces/${workspaceId}/graph`,
        authHeaders,
      ),
      fetchJSON<WorkspacePaperListResponse>(
        `/v1/workspaces/${workspaceId}/papers`,
        authHeaders,
      ),
      fetchJSON<WorkspaceJobListResponse>(
        `/v1/workspaces/${workspaceId}/jobs`,
        authHeaders,
      ),
      fetchJSON<WorkspaceBatchListResponse>(
        `/v1/workspaces/${workspaceId}/batches`,
        authHeaders,
      ),
    ]);

    return { meta, viewer, summary, graph, papers, jobs, batches };
  } catch {
    if (!demoFallbackEnabled()) {
      throw new Error(
        "Hypatia V2 could not reach the API, and demo fallback is disabled.",
      );
    }
    return {
      ...buildDemoWorkspaceBundle(workspaceId),
      meta: buildDemoMeta(),
      viewer: buildDemoViewer(),
    };
  }
}
