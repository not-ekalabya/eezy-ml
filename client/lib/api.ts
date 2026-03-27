export type BackendProject = {
  name: string;
  repo_url: string;
  github_token: string;
  instance_id: string;
};

type ApiErrorBody = {
  error?: string;
};

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:3000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init?.headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body.error) {
        message = body.error;
      }
    } catch {
      // ignore parse errors and keep generic message
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export async function listProjectsApi() {
  return request<{ projects: BackendProject[] }>("/project-manager/list");
}

export async function autoCreateProjectApi(payload: {
  name: string;
  repo_url: string;
  sub_folder: string;
  github_token: string;
  instance_type: string;
  isSpotInstance: boolean;
}) {
  const requestPayload = {
    ...payload,
    market_type: payload.isSpotInstance ? "spot" : "on-demand",
  };

  return request<{ message: string; project: BackendProject }>(
    "/project-manager/auto_create",
    {
      method: "POST",
      body: JSON.stringify(requestPayload),
    },
  );
}

export async function modifyProjectApi(payload: {
  name: string;
  repo_url: string;
  sub_folder: string;
  github_token: string;
  instance_id: string;
  isSpotInstance: boolean;
}) {
  return request<{ message: string; project: BackendProject }>(
    "/project-manager/modify",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function autoDeleteProjectApi(name: string) {
  return request<{ message: string; name: string }>(
    "/project-manager/auto_delete",
    {
      method: "POST",
      body: JSON.stringify({ name }),
    },
  );
}

export type SetupProjectResponse = {
  message: string;
  command_id: string;
  status: string;
  stdout: string;
  stderr: string;
  logs: string;
};

export type StartProjectResponse = {
  message: string;
  instance_id: string;
  status: string;
  command_id?: string;
  stdout?: string;
  stderr?: string;
  logs?: string;
};

export type ProjectLogsResponse = {
  logs: string;
  start_byte: number;
  next_byte: number;
  log_file_not_found: boolean;
  command_status: string;
  command_response_code: number | null;
  command_stderr: string;
};

export async function setupProjectApi(projectName: string) {
  return request<SetupProjectResponse>(
    `/projects/${encodeURIComponent(projectName)}/setup`,
    {
      method: "POST",
    },
  );
}

export async function startProjectApi(projectName: string) {
  return request<StartProjectResponse>(
    `/projects/${encodeURIComponent(projectName)}/start`,
    {
      method: "POST",
    },
  );
}

export type StopProjectResponse = {
  message: string;
  name: string;
  instance_id: string;
  status: string;
};

export async function stopProjectApi(projectName: string) {
  return request<StopProjectResponse>(
    `/projects/${encodeURIComponent(projectName)}/stop`,
    {
      method: "POST",
    },
  );
}

export async function getProjectLogsApi(payload: {
  projectName: string;
  commandId: string;
  startByte: number;
}) {
  const params = new URLSearchParams({
    command_id: payload.commandId,
    start_byte: String(payload.startByte),
  });

  return request<ProjectLogsResponse>(
    `/projects/${encodeURIComponent(payload.projectName)}/logs?${params.toString()}`,
  );
}

export type ProjectStatusResponse = {
  project_name: string;
  instance_id: string;
  state: string;
  public_ip: string | null;
  instance_type: string;
  service_status: string;
  inference_url: string | null;
};

export type ProjectFetchResponse = {
  name: string;
  repo_url: string;
  github_token: string;
  instance_id: string;
  sub_folder: string;
};

export async function getProjectStatusApi(projectName: string) {
  return request<ProjectStatusResponse>(
    `/projects/${encodeURIComponent(projectName)}/status`,
  );
}

export async function fetchProjectApi(projectName: string) {
  return request<ProjectFetchResponse>(
    `/projects/${encodeURIComponent(projectName)}/fetch`,
  );
}

export type ProjectPredictResponse = {
  project_name: string;
  instance_id: string;
  result: Record<string, unknown>;
};

export async function predictProjectApi(payload: {
  projectName: string;
  requestBody: Record<string, unknown>;
  signal?: AbortSignal;
}) {
  return request<ProjectPredictResponse>(
    `/projects/${encodeURIComponent(payload.projectName)}/predict`,
    {
      method: "POST",
      signal: payload.signal,
      body: JSON.stringify(payload.requestBody),
    },
  );
}
