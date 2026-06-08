import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Bell,
  Bus,
  FileText,
  Inbox,
  LayoutDashboard,
  Map,
  Route,
  Settings,
  Users,
} from "lucide-react";
import type { Role } from "@/lib/api/types";

export interface NavItem {
  to: string;
  /** i18n key in the `common` namespace (e.g. "nav.dashboard"). */
  labelKey: string;
  icon: LucideIcon;
  /** Match only the exact path (for index routes). */
  end?: boolean;
}

const parent: NavItem[] = [
  { to: "/parent", labelKey: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/parent/requests", labelKey: "nav.requests", icon: FileText },
  { to: "/parent/notifications", labelKey: "nav.notifications", icon: Bell },
];

const driver: NavItem[] = [
  { to: "/driver", labelKey: "nav.today", icon: Bus, end: true },
];

const admin: NavItem[] = [
  { to: "/admin", labelKey: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/fleet", labelKey: "nav.fleet", icon: Map },
  { to: "/admin/alerts", labelKey: "nav.alerts", icon: AlertTriangle },
  { to: "/admin/requests", labelKey: "nav.requests", icon: Inbox },
  { to: "/admin/routes", labelKey: "nav.routes", icon: Route },
  { to: "/admin/vehicles", labelKey: "nav.vehicles", icon: Bus },
  { to: "/admin/drivers", labelKey: "nav.drivers", icon: Users },
  { to: "/admin/settings", labelKey: "nav.settings", icon: Settings },
];

export function navForRole(role: Role): NavItem[] {
  switch (role) {
    case "parent":
      return parent;
    case "driver":
      return driver;
    case "school_admin":
    case "super_admin":
      return admin;
    default:
      return [];
  }
}

/** Base path each role lands on after login. */
export function homeForRole(role: Role): string {
  switch (role) {
    case "parent":
      return "/parent";
    case "driver":
      return "/driver";
    case "school_admin":
    case "super_admin":
      return "/admin";
    default:
      return "/login";
  }
}
