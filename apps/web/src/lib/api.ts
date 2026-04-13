import {
  buildDemoMeta,
  buildDemoPaperDetail,
  buildDemoRelationshipDetail,
  buildDemoWorkspaceBundle,
} from "./demoWorkspace";
import { getApiBaseUrl } from "./apiBaseUrl";
import type {
  APIMetaResponse,
  PaperDetailResponse,
  PaperRelationshipDetailResponse,
  ViewerSummary,
  WorkspaceBatchListResponse,
  WorkspaceBundle,
  WorkspaceGraphResponse,
  WorkspaceJobListResponse,
  WorkspacePaperListResponse,
  WorkspaceSnapshot,
  WorkspaceSummary,
} from "./types";
import { buildDemoViewer, type ViewerRequestHeaders } from "./viewer";

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

export async function getWorkspaceSnapshot(
  workspaceId: string,
  authHeaders: ViewerRequestHeaders,
  options?: {
    paperId?: string | null;
    relationshipId?: string | null;
  },
): Promise<WorkspaceSnapshot> {
  const selectedPaperId = options?.paperId ?? null;
  const selectedRelationshipId = options?.relationshipId ?? null;
  const workspace = await getWorkspaceBundle(workspaceId, authHeaders);
  const [selectedPaperResult, selectedRelationshipResult] = await Promise.allSettled([
    selectedPaperId ? getPaperDetail(workspaceId, selectedPaperId, authHeaders) : Promise.resolve(null),
    selectedRelationshipId
      ? getPaperRelationshipDetail(workspaceId, selectedRelationshipId, authHeaders)
      : Promise.resolve(null),
  ]);

  return {
    workspace,
    selectedPaper:
      selectedPaperResult.status === "fulfilled" ? selectedPaperResult.value : null,
    selectedRelationship:
      selectedRelationshipResult.status === "fulfilled"
        ? selectedRelationshipResult.value
        : null,
    polled_at: new Date().toISOString(),
  };
}

export async function getPaperDetail(
  workspaceId: string,
  paperId: string,
  authHeaders: ViewerRequestHeaders,
): Promise<PaperDetailResponse> {
  try {
    return await fetchJSON<PaperDetailResponse>(
      `/v1/workspaces/${workspaceId}/papers/${paperId}`,
      authHeaders,
    );
  } catch {
    if (!demoFallbackEnabled()) {
      throw new Error(
        "Hypatia V2 could not reach the paper detail API, and demo fallback is disabled.",
      );
    }
    const detail = buildDemoPaperDetail(workspaceId, paperId);
    if (!detail) {
      throw new Error(`No demo paper detail exists for ${paperId}.`);
    }
    return detail;
  }
}

export async function getPaperRelationshipDetail(
  workspaceId: string,
  relationshipId: string,
  authHeaders: ViewerRequestHeaders,
): Promise<PaperRelationshipDetailResponse> {
  try {
    return await fetchJSON<PaperRelationshipDetailResponse>(
      `/v1/workspaces/${workspaceId}/paper-relationships/${relationshipId}`,
      authHeaders,
    );
  } catch {
    if (!demoFallbackEnabled()) {
      throw new Error(
        "Hypatia V2 could not reach the relationship detail API, and demo fallback is disabled.",
      );
    }
    const detail = buildDemoRelationshipDetail(workspaceId, relationshipId);
    if (!detail) {
      throw new Error(`No demo relationship detail exists for ${relationshipId}.`);
    }
    return detail;
  }
}
