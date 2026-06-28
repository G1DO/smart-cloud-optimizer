"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import DashboardBar from "./bar/page";
import { getSessionUser, SessionUser } from "@/app/lib/session";

type DashboardLayoutProps = {
  children: React.ReactNode;
};

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const searchParams = useSearchParams();

  const [languageOpen, setLanguageOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [user, setUser] = useState<SessionUser>({
    userId: "synthetic-001",
    profileName: "synthetic-001",
    email: "synthetic-001@demo.opticloud.ai",
    awsAccountId: "SYNTHETIC-001",
    role: "Demo Workspace",
    image: "",
    awsConnections: [],
  });

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("optic-theme");
    if (savedTheme === "dark") {
      setIsDark(true);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("optic-theme", isDark ? "dark" : "light");
  }, [isDark]);

  useEffect(() => {
    const userIdFromUrl =
      searchParams.get("user_id") ||
      searchParams.get("userId") ||
      searchParams.get("demoUser");

    const sessionUser = getSessionUser(userIdFromUrl);
    setUser(sessionUser);
  }, [searchParams]);

  useEffect(() => {
    const syncUser = () => {
      setUser(getSessionUser());
    };

    window.addEventListener("storage", syncUser);
    window.addEventListener("optic-user-updated", syncUser as EventListener);

    return () => {
      window.removeEventListener("storage", syncUser);
      window.removeEventListener("optic-user-updated", syncUser as EventListener);
    };
  }, []);

  return (
    <div className={[
      "dashboard-shell",
      isDark ? "dashboard-dark" : "",
      sidebarOpen ? "sidebar-expanded" : "sidebar-collapsed",
    ]
      .filter(Boolean)
      .join(" ")}
    >
      <DashboardBar
        languageOpen={languageOpen}
        setLanguageOpen={setLanguageOpen}
        profileOpen={profileOpen}
        setProfileOpen={setProfileOpen}
        isDark={isDark}
        setIsDark={setIsDark}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        user={user}
      />


      <div className="dashboard-main">
        <main className="dashboard-content">{children}</main>
      </div>
    </div>
  );
}