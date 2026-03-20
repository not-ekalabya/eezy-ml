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
  github_token: string;
  instance_type: string;
}) {
  return request<{ message: string; project: BackendProject }>(
    "/project-manager/auto_create",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function modifyProjectApi(payload: {
  name: string;
  repo_url: string;
  github_token: string;
  instance_id: string;
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
