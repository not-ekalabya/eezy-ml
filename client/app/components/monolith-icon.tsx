import {
  ArrowLeft,
  Bell,
  BookOpen,
  Circle,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  Cpu,
  Database,
  Edit3,
  EllipsisVertical,
  EyeOff,
  FolderGit2,
  GitBranch,
  Globe,
  Info,
  Layers,
  Link2,
  Lock,
  Package,
  Play,
  Plus,
  Pause,
  Server,
  Terminal,
  Trash2,
  Search,
  type LucideIcon,
} from "lucide-react";

const ICON_MAP: Record<string, LucideIcon> = {
  notifications: Bell,
  help_outline: CircleHelp,
  stacks: Layers,
  settings: Server,
  dns: Server,
  add: Plus,
  play_arrow: Play,
  pause: Pause,
  contact_support: CircleHelp,
  menu_book: BookOpen,
  terminal: Terminal,
  database: Database,
  edit: Edit3,
  delete: Trash2,
  dashboard_customize: Layers,
  link: Link2,
  lock: Lock,
  info: Info,
  account_tree: GitBranch,
  more_vert: EllipsisVertical,
  warning: CircleAlert,
  inventory_2: Package,
  arrow_back: ArrowLeft,
  source: FolderGit2,
  visibility_off: EyeOff,
  memory: Cpu,
  check_circle: CircleCheck,
  circle: Circle,
  language: Globe,
  search: Search,
};

type MonolithIconProps = {
  name: string;
  className?: string;
};

export function MonolithIcon({ name, className }: MonolithIconProps) {
  const Icon = ICON_MAP[name] ?? Circle;

  return <Icon className={className} aria-hidden="true" strokeWidth={1.8} />;
}
