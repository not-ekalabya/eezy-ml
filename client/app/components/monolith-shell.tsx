import Link from "next/link";
import { MonolithIcon } from "@/app/components/monolith-icon";

type TopLink = {
  label: string;
  href: string;
};

type SideLink = {
  label: string;
  href: string;
  icon: string;
};

type MonolithShellProps = {
  children: React.ReactNode;
  topLinks: TopLink[];
  activeTopLink: string;
  sideLinks: SideLink[];
  activeSideLink: string;
  showCreateResource?: boolean;
};

export function MonolithShell({
  children,
  topLinks,
  activeTopLink,
  sideLinks,
  activeSideLink,
  showCreateResource = false,
}: MonolithShellProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-white/5 bg-[#131313] px-4 md:px-6">
        <div className="flex items-center gap-5 md:gap-8">
          <span className="text-base font-extrabold tracking-tighter text-white md:text-lg">
            MONOLITH CLOUD
          </span>
          <nav className="hidden items-center gap-6 text-sm md:flex">
            {topLinks.map((item) => {
              const active = item.label === activeTopLink;

              return (
                <Link
                  key={item.label}
                  href={item.href}
                  className={[
                    "pb-4 pt-4 transition-colors",
                    active
                      ? "border-b-2 border-white font-medium text-white"
                      : "text-neutral-400 hover:text-white",
                  ].join(" ")}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-2 md:gap-4">
          <button className="rounded-md p-2 text-white transition-colors hover:bg-white/5">
            <MonolithIcon name="notifications" className="h-5 w-5" />
          </button>
          <button className="rounded-md p-2 text-white transition-colors hover:bg-white/5">
            <MonolithIcon name="help_outline" className="h-5 w-5" />
          </button>
          <div className="h-8 w-8 overflow-hidden rounded-full border border-white/15 bg-gradient-to-br from-[#ffefcc] to-[#d9a673]" />
        </div>
      </header>

      <div className="flex min-h-[calc(100vh-64px)]">
        <aside className="hidden w-64 flex-col bg-[#1c1b1b] md:flex">
          <div className="px-6 pb-5 pt-6">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500">
              Console
            </p>
            <p className="text-xs text-neutral-400">Production Environment</p>
          </div>

          <nav className="flex flex-1 flex-col gap-2 px-2">
            {sideLinks.map((item) => {
              const active = item.label === activeSideLink;

              return (
                <Link
                  key={item.label}
                  href={item.href}
                  className={[
                    "mx-0 flex items-center gap-3 rounded-md px-3 py-2 text-[13px] font-medium tracking-wide transition-colors",
                    active
                      ? "bg-white/10 text-white"
                      : "text-neutral-500 hover:bg-white/5 hover:text-neutral-200",
                  ].join(" ")}
                >
                  <MonolithIcon name={item.icon} className="h-[18px] w-[18px]" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {showCreateResource ? (
            <button className="mx-4 mb-6 mt-2 flex items-center justify-center gap-2 rounded-md bg-white py-2.5 text-sm font-bold text-black transition-colors hover:bg-neutral-200">
              <MonolithIcon name="add" className="h-[18px] w-[18px]" />
              Create Resource
            </button>
          ) : null}

          <div className="mt-auto border-t border-white/5 pb-5 pt-4">
            <a className="mx-2 flex items-center gap-3 rounded-md px-3 py-2 text-[13px] text-neutral-500 transition-colors hover:bg-white/5 hover:text-neutral-200">
              <MonolithIcon name="contact_support" className="h-[18px] w-[18px]" />
              Support
            </a>
            <a className="mx-2 flex items-center gap-3 rounded-md px-3 py-2 text-[13px] text-neutral-500 transition-colors hover:bg-white/5 hover:text-neutral-200">
              <MonolithIcon name="menu_book" className="h-[18px] w-[18px]" />
              Documentation
            </a>
          </div>
        </aside>

        {children}
      </div>
    </div>
  );
}

export const sharedSideNav = [
  { label: "Projects", href: "/", icon: "stacks" },
//   { label: "Settings", href: "#", icon: "settings" },
//   { label: "Infrastructure", href: "#", icon: "dns" },
];
