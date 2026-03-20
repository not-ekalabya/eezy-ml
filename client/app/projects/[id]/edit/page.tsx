import Link from "next/link";
import {
  MonolithShell,
  sharedSideNav,
} from "@/app/components/monolith-shell";
import { currentConfig } from "@/app/components/monolith-data";
import { MonolithIcon } from "@/app/components/monolith-icon";

type EditProjectProps = {
  params: Promise<{ id: string }>;
};

export default async function EditProjectPage({ params }: EditProjectProps) {
  const { id } = await params;

  return (
    <MonolithShell
      topLinks={[
        { label: "Projects", href: "/" },
        { label: "Infrastructure", href: "#" },
        { label: "Settings", href: "#" },
      ]}
      activeTopLink="Projects"
      sideLinks={sharedSideNav}
      activeSideLink="Projects"
    >
      <main className="shell-grid min-h-[calc(100vh-64px)] flex-1 bg-[#131313] p-6 md:p-12 lg:p-20">
        <div className="mb-10">
          <Link
            href="/"
            className="group inline-flex items-center gap-2 text-sm text-[color:var(--on-surface-variant)] transition-colors hover:text-white"
          >
            <MonolithIcon
              name="arrow_back"
              className="h-4 w-4 transition-transform group-hover:-translate-x-1"
            />
            Back to Projects
          </Link>
        </div>

        <header className="mb-16">
          <div className="mb-3 flex items-baseline gap-4">
            <span className="bg-[color:var(--surface-container-highest)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-[color:var(--on-surface-variant)]">
              Editing Project
            </span>
            <span className="text-xs text-white/35">ID: {id}</span>
          </div>
          <h1 className="mb-4 text-4xl font-extrabold tracking-tighter text-white md:text-6xl">
            {id}
          </h1>
          <p className="max-w-2xl text-lg leading-relaxed text-[color:var(--on-surface-variant)]">
            Update your project architecture and environment variables. These
            changes will trigger a redeployment of all active containers.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-10 lg:grid-cols-12 lg:gap-16">
          <div className="space-y-14 lg:col-span-8">
            <section>
              <div className="mb-8 flex items-center gap-3">
                <MonolithIcon name="source" className="h-5 w-5 text-white" />
                <h3 className="text-xl font-semibold tracking-tight text-white">
                  Source Control
                </h3>
              </div>

              <div className="space-y-7">
                <div>
                  <label className="mb-3 block text-[11px] font-bold uppercase tracking-[0.1em] text-[color:var(--on-surface-variant)]">
                    GitHub Repository URL
                  </label>
                  <input
                    defaultValue="https://github.com/monolith-org/core-api-v2"
                    className="h-14 w-full bg-[color:var(--surface-container-highest)] px-4 text-white focus:outline-none"
                  />
                </div>

                <div>
                  <label className="mb-3 block text-[11px] font-bold uppercase tracking-[0.1em] text-[color:var(--on-surface-variant)]">
                    GitHub Access Token
                  </label>
                  <div className="relative">
                    <input
                      type="password"
                      defaultValue="ghp_************************"
                      className="h-14 w-full bg-[color:var(--surface-container-highest)] px-4 pr-12 text-white focus:outline-none"
                    />
                    <MonolithIcon
                      name="visibility_off"
                      className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 cursor-pointer text-white/50 transition hover:text-white"
                    />
                  </div>
                  <p className="mt-2 text-[11px] italic text-white/45">
                    Scoped permissions for repo and read:org required.
                  </p>
                </div>
              </div>
            </section>

            <section>
              <div className="mb-8 flex items-center gap-3">
                <MonolithIcon name="memory" className="h-5 w-5 text-white" />
                <h3 className="text-xl font-semibold tracking-tight text-white">
                  Compute Profile
                </h3>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-white bg-white p-6 text-black">
                  <div className="mb-4 flex items-start justify-between">
                    <span className="font-bold">t3.medium</span>
                    <MonolithIcon name="check_circle" className="h-5 w-5" />
                  </div>
                  <div className="mb-1 text-xs font-bold uppercase tracking-widest text-black/65">
                    Compute Capacity
                  </div>
                  <div className="text-2xl font-bold">4 vCPU / 8GB RAM</div>
                  <div className="mt-4 border-t border-black/10 pt-3 text-[10px] uppercase tracking-wider text-black/55">
                    Default Architecture
                  </div>
                </div>

                <div className="rounded-lg border border-white/15 bg-[color:var(--surface-container)] p-6 transition hover:border-white/35">
                  <div className="mb-4 flex items-start justify-between">
                    <span className="font-bold text-white">t3.large</span>
                    <MonolithIcon
                      name="circle"
                      className="h-5 w-5 text-[color:var(--on-surface-variant)]"
                    />
                  </div>
                  <div className="mb-1 text-xs font-bold uppercase tracking-widest text-white/65">
                    Compute Capacity
                  </div>
                  <div className="text-2xl font-bold text-white">8 vCPU / 16GB RAM</div>
                  <div className="mt-4 border-t border-white/10 pt-3 text-[10px] uppercase tracking-wider text-white/45">
                    Premium Architecture
                  </div>
                </div>
              </div>
            </section>

            <div className="flex items-center gap-6 pt-6">
              <button className="h-12 bg-white px-8 font-bold text-black transition hover:bg-neutral-200">
                Save Changes
              </button>
              <button className="font-medium text-[color:var(--on-surface-variant)] transition hover:text-white">
                Cancel
              </button>
            </div>
          </div>

          <aside className="lg:col-span-4">
            <div className="sticky top-28 space-y-6">
              <div className="bg-[color:var(--surface-container-low)] p-7">
                <h4 className="mb-6 text-xs font-extrabold uppercase tracking-widest text-white/45">
                  Current Config
                </h4>
                <ul className="space-y-5">
                  {currentConfig.map((item) => (
                    <li key={item.label} className="flex items-center justify-between gap-2">
                      <span className="text-sm text-[color:var(--on-surface-variant)]">
                        {item.label}
                      </span>
                      <span className="text-sm font-medium text-white">{item.value}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-8 border-t border-white/10 pt-6">
                  <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-[color:var(--error)]">
                    <MonolithIcon name="warning" className="h-4 w-4" />
                    Irreversible Actions
                  </div>
                  <Link
                    href={`/projects/${id}/delete`}
                    className="mt-4 block text-xs font-medium text-[color:var(--error)]/70 underline transition hover:text-[color:var(--error)]"
                  >
                    Delete project &apos;{id}&apos;
                  </Link>
                </div>
              </div>

              <div className="bg-[color:var(--surface-container-lowest)] p-6">
                <div className="mb-4 flex items-center justify-between">
                  <h4 className="text-[10px] font-extrabold uppercase tracking-widest text-white/40">
                    Environment Status
                  </h4>
                  <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                </div>
                <p className="text-[13px] leading-snug text-white/90">
                  Production cluster is currently stable. Updates will be applied
                  sequentially across <span className="font-bold">3 zones</span>.
                </p>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </MonolithShell>
  );
}
