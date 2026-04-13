import { WorkspaceLiveShell } from "../../../components/workspaceLiveShell";
import { getWorkspaceSnapshot } from "../../../lib/api";
import { getViewerRequestHeaders } from "../../../lib/viewer";

type WorkspacePageProps = {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{
    paper?: string | string[];
    relationship?: string | string[];
  }>;
};

function firstSearchValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default async function WorkspacePage({
  params,
  searchParams,
}: WorkspacePageProps) {
  const { workspaceId } = await params;
  const resolvedSearchParams = await searchParams;
  const authHeaders = await getViewerRequestHeaders();
  const snapshot = await getWorkspaceSnapshot(workspaceId, authHeaders, {
    paperId: firstSearchValue(resolvedSearchParams.paper),
    relationshipId: firstSearchValue(resolvedSearchParams.relationship),
  });

  return <WorkspaceLiveShell workspaceId={workspaceId} initialSnapshot={snapshot} />;
}
