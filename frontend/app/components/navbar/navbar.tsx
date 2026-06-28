"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import "./navbar.css";

function getInitialDarkMode() {
  if (typeof window === "undefined") return false;

  const savedTheme = localStorage.getItem("optic-theme");
  if (savedTheme) return savedTheme === "dark";

  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export default function Navbar() {
  const [languageOpen, setLanguageOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(getInitialDarkMode);
  const pathname = usePathname();

  const applyTheme = (enabled: boolean) => {
    if (typeof window === "undefined") return;

    document.documentElement.classList.toggle("optic-dark", enabled);
    document.body.classList.toggle("optic-dark", enabled);
    localStorage.setItem("optic-theme", enabled ? "dark" : "light");
  };

  useEffect(() => {
    applyTheme(isDarkMode);
  }, [isDarkMode]);

  const handleLogoClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (pathname === "/") {
      e.preventDefault();
      window.location.reload();
    }
  };

  const handleThemeToggle = () => {
    setIsDarkMode((currentMode) => !currentMode);
  };

  return (
    <header className="navbar-wrapper">
      <div className="topbar">
        <div className="topbar-right">
          <button
            className={`topbar-action theme-action ${isDarkMode ? "active" : ""}`}
            aria-label={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
            type="button"
            onClick={handleThemeToggle}
            title={isDarkMode ? "Light mode" : "Dark mode"}
          >
            <Image src="/icons/dark.png" alt="Dark Mode" width={18} height={18} />
          </button>

          <div className="language-dropdown">
            <button
              className="topbar-action language-trigger"
              aria-label="Languages"
              type="button"
              onClick={() => setLanguageOpen(!languageOpen)}
            >
              <Image
                src="/icons/language.png"
                alt="Languages"
                width={18}
                height={18}
              />
            </button>

            {languageOpen && (
              <div className="language-menu">
                <button className="language-item active" type="button">
                  English
                </button>
                <button className="language-item" type="button">
                  Arabic
                </button>
                <button className="language-item" type="button">
                  German
                </button>
              </div>
            )}
          </div>

          <button className="topbar-action" aria-label="Settings" type="button">
            <Image
              src="/icons/settings.png"
              alt="Settings"
              width={18}
              height={18}
            />
          </button>
        </div>
      </div>

      <div className="navbar">
        <Link href="/" onClick={handleLogoClick} className="logo-wrapper logo-link">
          <div className="logo-text-wrapper">
            <h1 className="logo-text space-font">
              <Image
                src="/icons/logo.png"
                alt="logo"
                width={90}
                height={40}
                className="logo-img"
                style={{ background: "transparent" }}
              />
              <span className="brand-main">OptiCloud</span>
            </h1>
            <p className="logo-sub inter-font">AWS Cloud Cost Optimizer</p>
          </div>
        </Link>

        <nav className="nav-links inter-font">
          <Link href="/" className="nav-item">Home</Link>
          <Link href="/dashboard/costs" className="nav-item">Costs</Link>
          <Link href="/dashboard/forecasts" className="nav-item">Forecasts</Link>
          <Link href="/dashboard/recommendations" className="nav-item">Recommendations</Link>
          <a className="nav-item">About</a>
        </nav>

        <div className="nav-actions">
          <Link href="/authentication/login" className="btn-auth-login">
            Log In
          </Link>
          <Link href="/authentication/signup" className="btn-auth-signup">
            Sign Up
          </Link>
        </div>
      </div>
    </header>
  );
}
