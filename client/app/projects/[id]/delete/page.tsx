"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import {
  MonolithShell,
  sharedSideNav,
} from "@/app/components/monolith-shell";
import { MonolithIcon } from "@/app/components/monolith-icon";
import { autoDeleteProjectApi } from "@/lib/api";

export default function DeleteProjectPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    setDeleting(true);
    setError(null);
    try {
      await autoDeleteProjectApi(id);
      router.push("/");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete project");
      setDeleting(false);
    }
  }

  return (
    <MonolithShell
      topLinks={[
        { label: "Projects", href: "/" },
        { label: "Infrastructure", href: "#" },
        { label: "Usage", href: "#" },
      ]}
      activeTopLink="Projects"
      sideLinks={sharedSideNav}
      activeSideLink="Projects"
      showCreateResource
    >
      <main className="relative min-h-[calc(100vh-64px)] flex-1 overflow-hidden bg-[#131313] p-8">
        <div className="pointer-events-none mx-auto max-w-6xl opacity-20">
          <div className="mb-12">
            <h1 className="mb-2 text-4xl font-extrabold tracking-tighter text-white">
              Projects
            </h1>
            <p className="text-[color:var(--on-surface-variant)]">
              Manage your cloud infrastructure deployments.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="rounded-lg border border-white/10 bg-[color:var(--surface-container)] p-8 lg:col-span-8">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="text-xl">Active Deployments</h3>
                <span className="bg-white/5 px-2 py-1 text-[10px] uppercase tracking-widest">
                  Live Status
                </span>
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between rounded bg-[color:var(--surface-container-low)] p-4">
                  <div className="flex items-center gap-4">
                    <MonolithIcon name="account_tree" className="h-5 w-5" />
                    <div>
                      <p className="font-medium text-white">Quantum-Edge-API</p>
                      <p className="text-xs text-[color:var(--on-surface-variant)]">
                        Last deployed 2h ago
                      </p>
                    </div>
                  </div>
                  <MonolithIcon name="more_vert" className="h-5 w-5" />
                </div>
                <div className="flex items-center justify-between rounded bg-[color:var(--surface-container-low)] p-4">
                  <div className="flex items-center gap-4">
                    <MonolithIcon name="database" className="h-5 w-5" />
                    <div>
                      <p className="font-medium text-white">Main-Storage-Cluster</p>
                      <p className="text-xs text-[color:var(--on-surface-variant)]">
                        Syncing data...
                      </p>
                    </div>
                  </div>
                  <MonolithIcon name="more_vert" className="h-5 w-5" />
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-[color:var(--surface-container-low)] p-6 lg:col-span-4">
              <span className="text-[10px] uppercase tracking-widest text-[color:var(--on-surface-variant)]">
                Usage Limit
              </span>
              <p className="mt-4 text-3xl">84.2%</p>
              <div className="mt-4 h-1 w-full bg-[color:var(--surface-container-highest)]">
                <div className="h-full w-[84%] bg-white" />
              </div>
              <button className="mt-8 w-full border border-white/25 py-2 text-sm font-medium transition hover:bg-white/5">
                Upgrade Plan
              </button>
            </div>
          </div>
        </div>

        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/75 p-6 backdrop-blur-sm">
          <div className="glass-dark w-full max-w-md rounded-xl p-8 shadow-[0px_20px_40px_rgba(0,0,0,0.45)]">
            <div className="mb-6 flex flex-col items-center text-center">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-[color:var(--error)]/10">
                <MonolithIcon
                  name="warning"
                  className="h-8 w-8 text-[color:var(--error)]"
                />
              </div>
              <h2 className="mb-2 text-2xl font-bold text-white">Delete Project</h2>
              <p className="text-[color:var(--on-surface-variant)]">
                Are you sure you want to delete this project? This action is
                irreversible and all associated data will be permanently removed.
              </p>
            </div>

            <div className="mb-6 rounded-lg border border-white/10 bg-[color:var(--surface-container-lowest)] p-4">
              <div className="flex items-center gap-2">
                <MonolithIcon
                  name="inventory_2"
                  className="h-4 w-4 text-[color:var(--on-surface-variant)]"
                />
                <span className="font-mono text-xs uppercase tracking-wider text-[color:var(--on-surface-variant)]">
                  Project ID: {id}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="flex-1 rounded-lg border border-white/15 py-3 text-center text-sm font-medium text-white transition hover:bg-[color:var(--surface-container-highest)]"
              >
                Cancel
              </Link>
              <button
                onClick={onDelete}
                disabled={deleting}
                className="flex-1 rounded-lg bg-white py-3 text-sm font-bold text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>

            {error ? (
              <p className="mt-3 text-center text-sm text-[color:var(--error)]">{error}</p>
            ) : null}
          </div>
        </div>
      </main>
    </MonolithShell>
  );
}
