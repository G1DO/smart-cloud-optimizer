"use client";

import { useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import "../bar/bar.css";
import { clearSessionUser, SessionUser } from "@/app/lib/session";

type NavKey = "home" | "costs" | "forecasts" | "recommendations";

type DashboardBarProps = {
  languageOpen: boolean;
  setLanguageOpen: React.Dispatch<React.SetStateAction<boolean>>;
  profileOpen: boolean;
  setProfileOpen: React.Dispatch<React.SetStateAction<boolean>>;
  isDark: boolean;
  setIsDark: React.Dispatch<React.SetStateAction<boolean>>;
  sidebarOpen: boolean;
  setSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
  user: SessionUser;
};

type AwsConnectionLike = {
  id?: string;
  connectionName?: string;
  connection_name?: string;
  accountName?: string;
  account_name?: string;
  awsAccountId?: string;
  aws_account_id?: string;
  primaryRegion?: string;
  primary_region?: string;
  region?: string;
  aws_region?: string;
  name?: string;
};

function firstNonEmpty(...values: Array<unknown>): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function getAwsConnections(user: SessionUser): AwsConnectionLike[] {
  const unsafeUser = user as SessionUser & {
    awsConnections?: unknown;
    aws_connections?: unknown;
  };

  const raw = unsafeUser.awsConnections ?? unsafeUser.aws_connections ?? [];
  return Array.isArray(raw) ? (raw as AwsConnectionLike[]) : [];
}

function getWorkspaceLabel(user: SessionUser): string {
  const unsafeUser = user as SessionUser & {
    demoMode?: boolean;
    demo_mode?: boolean;
    userId?: string;
    user_id?: string;
    selectedUser?: string;
    selected_user?: string;
  };

  const isDemoUser =
    unsafeUser.demoMode === true ||
    unsafeUser.demo_mode === true ||
    unsafeUser.userId === "aws-SYNTHETIC-001" ||
    unsafeUser.user_id === "aws-SYNTHETIC-001" ||
    unsafeUser.selectedUser === "aws-SYNTHETIC-001" ||
    unsafeUser.selected_user === "aws-SYNTHETIC-001";

  if (isDemoUser) {
    return "Demo AWS Account";
  }

  const connections = getAwsConnections(user);

  if (!connections.length) {
    return "No AWS Connection";
  }

  const firstConnection = connections[0];

  const connectionLabel = firstNonEmpty(
    firstConnection.connectionName,
    firstConnection.connection_name,
    firstConnection.accountName,
    firstConnection.account_name,
    firstConnection.name,
    firstConnection.awsAccountId,
    firstConnection.aws_account_id,
    "AWS Connection"
  );

  const regionLabel = firstNonEmpty(
    firstConnection.primaryRegion,
    firstConnection.primary_region,
    firstConnection.region,
    firstConnection.aws_region
  );

  return regionLabel ? `${connectionLabel} • ${regionLabel}` : connectionLabel;
}

export default function DashboardBar({
  languageOpen,
  setLanguageOpen,
  profileOpen,
  setProfileOpen,
  isDark,
  setIsDark,
  sidebarOpen,
  setSidebarOpen,
  user,
}: DashboardBarProps) {
  const profileRef = useRef<HTMLDivElement | null>(null);
  const languageRef = useRef<HTMLDivElement | null>(null);
  const pathname = usePathname();
  const router = useRouter();

  const activeNav: NavKey =
    pathname === "/dashboard/costs"
      ? "costs"
      : pathname === "/dashboard/forecasts"
        ? "forecasts"
        : pathname === "/dashboard/recommendations"
          ? "recommendations"
          : "home";

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;

      if (profileRef.current && !profileRef.current.contains(target)) {
        setProfileOpen(false);
      }

      if (languageRef.current && !languageRef.current.contains(target)) {
        setLanguageOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [setLanguageOpen, setProfileOpen]);

  useEffect(() => {
    setLanguageOpen(false);
    setProfileOpen(false);
  }, [pathname, setLanguageOpen, setProfileOpen]);

  const openAccountSettings = () => {
    setProfileOpen(false);
    router.push("/dashboard/account-settings?tab=profile");
  };

  const openManageConnections = () => {
    setProfileOpen(false);
    router.push("/dashboard/account-settings?tab=connections");
  };

  const handleLogout = () => {
    clearSessionUser();
    setProfileOpen(false);
    router.push("/");
  };

  const handleBrandHomeRefresh = () => {
    setLanguageOpen(false);
    setProfileOpen(false);
    router.push("/dashboard/home");
    router.refresh();
  };

  const unsafeUser = user as SessionUser & {
    profile_name?: string;
    role?: string;
    image?: string;
    email?: string;
  };

  const displayedName = firstNonEmpty(
    user.profileName,
    unsafeUser.profile_name,
    "synthetic-001"
  );

  const displayedRole = firstNonEmpty(
    user.role,
    unsafeUser.role,
    "Demo Workspace"
  );

  const displayedEmail = firstNonEmpty(
    user.email,
    unsafeUser.email,
    "demo@aws.local"
  );

  const displayedImage = firstNonEmpty(user.image, unsafeUser.image);

  const workspaceLabel = useMemo(() => getWorkspaceLabel(user), [user]);

  return (
    <>
      <aside
        className={`dashboard-sidebar ${sidebarOpen ? "expanded" : "collapsed"}`}
      >
        <div className="sidebar-top-zone">
          <div className="sidebar-brand-bar">
            <button
              type="button"
              className="sidebar-brand-home-btn"
              onClick={handleBrandHomeRefresh}
              aria-label="Go to dashboard home and refresh"
              title="Dashboard Home"
            >
              <div className="sidebar-brand-left">
                <img
                  src="/icons/logo.png"
                  alt="OptiCloud logo"
                  className="sidebar-brand-logo"
                />
                {sidebarOpen && <span className="sidebar-brand-name">OptiCloud</span>}
              </div>
            </button>

            <button
              className="sidebar-brand-arrow"
              type="button"
              aria-label="Toggle sidebar"
              onClick={() => setSidebarOpen((prev) => !prev)}
            >
              <svg
                viewBox="0 0 24 24"
                className="sidebar-arrow-svg"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
              >
                {sidebarOpen ? <path d="M15 6l-6 6 6 6" /> : <path d="M9 6l6 6-6 6" />}
              </svg>
            </button>
          </div>

          <nav className="dashboard-nav">
            <Link
              href="/dashboard/home"
              className={`dashboard-nav-item ${activeNav === "home" ? "active" : ""}`}
            >
              <span className="nav-item-icon">
                <img
                  src="/icons/sidebar/home.png"
                  alt="dashboard"
                  className="sidebar-icon-img"
                />
              </span>
              {sidebarOpen && <span className="nav-item-text">Dashboard</span>}
            </Link>

            <Link
              href="/dashboard/costs"
              className={`dashboard-nav-item ${activeNav === "costs" ? "active" : ""}`}
            >
              <span className="nav-item-icon">
                <img
                  src="/icons/sidebar/cost.png"
                  alt="costs"
                  className="sidebar-icon-img"
                />
              </span>
              {sidebarOpen && <span className="nav-item-text">Costs</span>}
            </Link>

            <Link
              href="/dashboard/forecasts"
              className={`dashboard-nav-item ${activeNav === "forecasts" ? "active" : ""}`}
            >
              <span className="nav-item-icon">
                <img
                  src="/icons/sidebar/forecast.png"
                  alt="forecasts"
                  className="sidebar-icon-img"
                />
              </span>
              {sidebarOpen && <span className="nav-item-text">Forecasts</span>}
            </Link>

            <Link
              href="/dashboard/recommendations"
              className={`dashboard-nav-item ${activeNav === "recommendations" ? "active" : ""
                }`}
            >
              <span className="nav-item-icon">
                <img
                  src="/icons/sidebar/rec.png"
                  alt="recommendations"
                  className="sidebar-icon-img"
                />
              </span>
              {sidebarOpen && <span className="nav-item-text">Recommendations</span>}
            </Link>
          </nav>
        </div>

        <div className="sidebar-bottom-zone">
          {sidebarOpen && (
            <div className="sidebar-workspace-block">
              <div className="sidebar-workspace-title">Workspace</div>

              <button
                type="button"
                className="sidebar-workspace-pill"
                onClick={openManageConnections}
              >
                <span className="workspace-icon-wrap">
                  <img src="/icons/sidebar/aws.png" alt="aws" className="sidebar-icon-img" />
                </span>

                <span className="workspace-pill-text">{workspaceLabel}</span>

                <span className="workspace-chevron">▾</span>
              </button>
            </div>
          )}

          <div className="sidebar-secondary-links">
            <button type="button" className="sidebar-secondary-item">
              <span className="sidebar-secondary-icon">
                <img
                  src="/icons/sidebar/support.png"
                  alt="support"
                  className="sidebar-icon-img"
                />
              </span>
              {sidebarOpen && <span>Support</span>}
            </button>
          </div>

          <button
            type="button"
            className="sidebar-account-card"
            onClick={openAccountSettings}
          >
            <div className="sidebar-account-avatar">
              {displayedImage ? (
                <img
                  src={displayedImage}
                  alt={displayedName}
                  className="sidebar-account-image"
                />
              ) : (
                <img
                  src="/icons/sidebar/profile.png"
                  alt="profile"
                  className="sidebar-icon-img"
                />
              )}
            </div>

            {sidebarOpen && (
              <>
                <div className="sidebar-account-copy">
                  <strong>{displayedName}</strong>
                  <span>{displayedRole}</span>
                </div>
                <span className="sidebar-account-chevron">›</span>
              </>
            )}
          </button>
        </div>
      </aside>

      <header className="dashboard-topbar">
        <div className="topbar-left">
          <div className="topbar-search">
            <span className="topbar-search-icon">
              <img
                src="/icons/topbar/search.png"
                alt="search"
                className="topbar-icon-img"
              />
            </span>
            <input type="text" placeholder="Search anything..." />
          </div>
        </div>

        <div className="topbar-right">
          <div className="topbar-control-wrap">
            <button
              className="topbar-icon-btn topbar-hover-match has-badge"
              type="button"
              aria-label="Notifications"
            >
              <span className="topbar-control-hover-ring">
                <img
                  src="/icons/topbar/notification.png"
                  alt="notification"
                  className="topbar-icon-img"
                />
              </span>
              <span className="topbar-badge">3</span>
            </button>
          </div>

          <div className="topbar-pop-wrap" ref={languageRef}>
            <button
              className="topbar-icon-btn topbar-hover-match"
              type="button"
              aria-label="Language"
              onClick={() => setLanguageOpen((prev) => !prev)}
            >
              <span className="topbar-control-hover-ring">
                <img src="/icons/language.png" alt="language" className="topbar-icon-img" />
              </span>
            </button>

            {languageOpen && (
              <div className="dashboard-language-menu">
                <button className="dashboard-language-item active" type="button">
                  English
                </button>
                <button className="dashboard-language-item" type="button">
                  Arabic
                </button>
                <button className="dashboard-language-item" type="button">
                  German
                </button>
              </div>
            )}
          </div>

          <div className="topbar-control-wrap">
            <button
              className="topbar-icon-btn topbar-hover-match"
              type="button"
              aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
              title={isDark ? "Switch to light mode" : "Switch to dark mode"}
              onClick={() => setIsDark((prev) => !prev)}
            >
              <span className="topbar-control-hover-ring">
                <img
                  src={isDark ? "/icons/topbar/sun.png" : "/icons/dark.png"}
                  alt={isDark ? "light mode" : "dark mode"}
                  className="topbar-icon-img topbar-theme-icon-img"
                />
              </span>
            </button>
          </div>

          <div className="topbar-profile-wrap" ref={profileRef}>
            <button
              className="topbar-profile-trigger avatar-only-trigger"
              type="button"
              onClick={() => setProfileOpen((prev) => !prev)}
              aria-label="Open profile menu"
            >
              <span className="topbar-avatar-hover-ring">
                <span className="topbar-user-avatar avatar-only">
                  {displayedImage ? (
                    <img
                      src={displayedImage}
                      alt={displayedName}
                      className="topbar-user-image"
                    />
                  ) : (
                    <img
                      src="/icons/sidebar/profile.png"
                      alt="profile"
                      className="topbar-icon-img"
                    />
                  )}
                </span>
              </span>
            </button>

            {profileOpen && (
              <div className="profile-dropdown">
                <div className="profile-dropdown-top">
                  <div className="profile-dropdown-avatar">
                    {displayedImage ? (
                      <img
                        src={displayedImage}
                        alt={displayedName}
                        className="profile-dropdown-image"
                      />
                    ) : (
                      <img
                        src="/icons/sidebar/profile.png"
                        alt="profile"
                        className="topbar-icon-img"
                      />
                    )}
                  </div>

                  <h3>{displayedName}</h3>
                  <p>{displayedEmail}</p>
                  <span>{displayedRole}</span>
                </div>

                <div className="profile-dropdown-section">
                  <button
                    className="profile-menu-item"
                    type="button"
                    onClick={openAccountSettings}
                  >
                    Account settings
                  </button>

                  <button
                    className="profile-menu-item"
                    type="button"
                    onClick={openManageConnections}
                  >
                    Manage AWS connections
                  </button>
                </div>

                <div className="profile-dropdown-footer">
                  <button className="profile-logout-btn" type="button" onClick={handleLogout}>
                    <img
                      src="/icons/topbar/logout.png"
                      alt="logout"
                      className="topbar-icon-img"
                    />
                    <span>Logout</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>
    </>
  );
}