import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Menu, MoreHorizontal } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Wordmark } from "@/components/common/Brand";
import { NotificationBell } from "@/components/common/NotificationBell";
import { UserMenu } from "@/components/common/UserMenu";
import { ConnectionBanner } from "@/components/common/ConnectionBanner";
import { SocketBridge } from "@/components/common/SocketBridge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useAuthStore } from "@/stores/auth";
import { navForRole, type NavItem } from "./navConfig";
import { cn } from "@/lib/utils";

export function AppLayout() {
  const { t } = useTranslation("common");
  const user = useAuthStore((s) => s.user);
  const [sheetOpen, setSheetOpen] = useState(false);

  const items = user ? navForRole(user.role) : [];
  // Mobile bottom bar: show up to 4 items inline, overflow into a "More" sheet.
  const inline = items.length > 5 ? items.slice(0, 4) : items;
  const hasMore = items.length > 5;

  return (
    <div className="flex min-h-screen flex-col bg-muted/30">
      <SocketBridge />

      {/* Mobile header */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background px-3 md:hidden">
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Menu">
              <Menu className="size-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-72 p-0">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <div className="flex h-14 items-center px-4">
              <Wordmark />
            </div>
            <NavList items={items} onNavigate={() => setSheetOpen(false)} />
          </SheetContent>
        </Sheet>
        <Wordmark />
        <NotificationBell />
      </header>

      <ConnectionBanner />

      <div className="flex flex-1">
        {/* Desktop sidebar */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-background md:flex">
          <div className="flex h-16 items-center px-5">
            <Wordmark />
          </div>
          <NavList items={items} className="flex-1 px-3" />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Desktop top bar */}
          <div className="hidden h-16 items-center justify-end gap-1 border-b border-border bg-background px-6 md:flex">
            <NotificationBell />
            <UserMenu />
          </div>

          <main className="flex-1 pb-24 md:pb-0">
            <div className="mx-auto w-full max-w-6xl p-4 md:p-6">
              <Outlet />
            </div>
          </main>
        </div>
      </div>

      {/* Mobile bottom nav */}
      {items.length > 1 ? (
        <nav className="fixed bottom-0 left-0 right-0 z-30 flex border-t border-border bg-background md:hidden">
          {inline.map((item) => (
            <BottomTab key={item.to} item={item} />
          ))}
          {hasMore ? (
            <button
              type="button"
              onClick={() => setSheetOpen(true)}
              className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium text-muted-foreground"
            >
              <MoreHorizontal className="size-5" />
              {t("actions.viewAll")}
            </button>
          ) : null}
        </nav>
      ) : null}
    </div>
  );
}

function NavList({
  items,
  className,
  onNavigate,
}: {
  items: NavItem[];
  className?: string;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation("common");
  return (
    <nav className={cn("space-y-1 p-2", className)}>
      {items.map(({ to, labelKey, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              isActive
                ? "bg-secondary text-secondary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )
          }
        >
          <Icon className="size-5 shrink-0" />
          {t(labelKey)}
        </NavLink>
      ))}
    </nav>
  );
}

function BottomTab({ item }: { item: NavItem }) {
  const { t } = useTranslation("common");
  const { icon: Icon } = item;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        cn(
          "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium",
          isActive ? "text-primary" : "text-muted-foreground",
        )
      }
    >
      <Icon className="size-5" />
      {t(item.labelKey)}
    </NavLink>
  );
}
