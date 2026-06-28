"use client";

import "./signup.css";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type AuthResponse = {
  success: boolean;
  message: string;
  user_id?: string | null;
  email?: string | null;
  profile_name?: string | null;
  demo_mode?: boolean;
  selected_user?: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PASSWORD_PATTERN = /^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;
const AUTH_REQUEST_TIMEOUT_MS = 12_000;

function validateEmail(value: string) {
  return EMAIL_PATTERN.test(value.trim());
}

function validatePassword(value: string) {
  return PASSWORD_PATTERN.test(value);
}

function persistAuth(data: AuthResponse) {
  if (typeof window === "undefined") return;

  const userId = data.selected_user || data.user_id || "";
  const profileName = data.profile_name || data.email?.split("@")[0] || "Workspace User";
  const isDemo = data.demo_mode === true;

  localStorage.setItem("isLoggedIn", "true");
  localStorage.setItem("auth_user_id", userId);
  localStorage.setItem("auth_email", data.email ?? "");
  localStorage.setItem("auth_display_name", profileName);
  localStorage.setItem("demo_mode", isDemo ? "true" : "false");

  if (data.selected_user) {
    localStorage.setItem("selected_user", data.selected_user);
    sessionStorage.setItem("selected_user", data.selected_user);
  } else {
    localStorage.removeItem("selected_user");
    localStorage.removeItem("selectedUser");
    sessionStorage.removeItem("selected_user");
    sessionStorage.removeItem("selectedUser");
  }

  localStorage.setItem(
    "opticloud_current_user",
    JSON.stringify({
      userId,
      profileName,
      email: data.email ?? "",
      awsAccountId: isDemo ? "SYNTHETIC-001" : "",
      role: isDemo ? "Demo Workspace" : "Workspace",
      image: "",
      awsConnections: [],
    })
  );
}

async function readJsonSafe(response: Response) {
  const text = await response.text();

  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { detail: text || "Invalid server response." };
  }
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = AUTH_REQUEST_TIMEOUT_MS
) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        "Signup is taking too long. Please make sure the backend server is running, then try again."
      );
    }

    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export default function SignUpPage() {
  const router = useRouter();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const isDisabled = useMemo(
    () => loading || demoLoading,
    [loading, demoLoading]
  );

  useEffect(() => {
    const savedTheme = localStorage.getItem("optic-theme");
    const isDark = savedTheme === "dark";

    document.documentElement.classList.toggle("optic-dark", isDark);
    document.body.classList.toggle("optic-dark", isDark);
  }, []);

  async function handleSignup(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setSuccessMessage("");

    if (!displayName.trim()) {
      setError("Display name is required.");
      return;
    }

    if (!email.trim() || !password || !confirmPassword) {
      setError("Display name, email, password, and confirmation are required.");
      return;
    }

    if (!validateEmail(email)) {
      setError("Please enter a valid email address.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (!validatePassword(password)) {
      setError(
        "Password must be at least 8 characters and include an uppercase letter, a number, and a symbol."
      );
      return;
    }

    setLoading(true);

    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/auth/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        cache: "no-store",
        body: JSON.stringify({
          display_name: displayName.trim(),
          email: email.trim(),
          password,
          confirm_password: confirmPassword,
        }),
      });

      const data = await readJsonSafe(response);

      if (!response.ok) {
        throw new Error(data.detail || data.message || "Signup failed.");
      }

      persistAuth(data);
      setSuccessMessage(data.message || "Account created successfully.");
      router.push("/dashboard/home");
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Unable to connect to the server.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDemoMode() {
    setError("");
    setSuccessMessage("");
    setDemoLoading(true);

    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/auth/demo`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        cache: "no-store",
      });

      const data = await readJsonSafe(response);

      if (!response.ok) {
        throw new Error(data.detail || data.message || "Demo mode failed.");
      }

      persistAuth(data);
      setSuccessMessage(data.message || "Demo mode activated.");
      router.push("/dashboard/home");
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Unable to connect to the server.";
      setError(message);
    } finally {
      setDemoLoading(false);
    }
  }

  return (
    <main className="signup-page">
      <div className="auth-bg">
        <div className="auth-blob auth-blob-1" />
        <div className="auth-blob auth-blob-2" />
        <div className="auth-blob auth-blob-3" />
        <div className="auth-blob auth-blob-4" />
        <div className="auth-blob auth-blob-5" />
        <div className="auth-blob auth-blob-6" />
        <div className="auth-blob auth-blob-7" />
        <div className="auth-blob auth-blob-8" />
        <div className="auth-blob auth-blob-9" />
        <div className="auth-blob auth-blob-10" />
      </div>

      <Link href="/" className="auth-top-logo">
        <Image
          src="/icons/logo.png?v=original"
          alt="OptiCloud logo"
          width={100}
          height={100}
          className="auth-top-logo-img"
          style={{ filter: "none", mixBlendMode: "normal" }}
          unoptimized
          priority
        />
      </Link>

      <section className="signup-shell">
        <div className="signup-left glass-card">
          <div className="brand-wrap">
            <h1 className="signup-title">Create Account</h1>
            <p className="signup-subtitle">
              Sign up to start monitoring usage, managing cloud costs, and
              accessing smarter optimization insights
            </p>
          </div>

          <form className="signup-form" onSubmit={handleSignup}>
            <div className="input-group">
              <label htmlFor="displayName">Display Name</label>
              <input
                id="displayName"
                type="text"
                placeholder="Enter your display name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={isDisabled}
                autoComplete="name"
                required
              />
            </div>

            <div className="input-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isDisabled}
                autoComplete="email"
                required
              />
            </div>

            <div className="input-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isDisabled}
                autoComplete="new-password"
                minLength={8}
                required
              />
              <span className="field-hint">
                8+ characters with uppercase, number, and symbol.
              </span>
            </div>

            <div className="input-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <input
                id="confirmPassword"
                type="password"
                placeholder="Confirm your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isDisabled}
                autoComplete="new-password"
                minLength={8}
                required
              />
            </div>

            {error ? <div className="auth-message auth-error">{error}</div> : null}
            {successMessage ? (
              <div className="auth-message auth-success">{successMessage}</div>
            ) : null}

            <button type="submit" className="primary-btn" disabled={isDisabled}>
              {loading ? "Creating Account..." : "Create Account"}
            </button>

            <button
              type="button"
              className="secondary-btn"
              onClick={handleDemoMode}
              disabled={isDisabled}
            >
              {demoLoading ? "Starting Demo..." : "Try Demo Mode"}
            </button>
          </form>

          <p className="bottom-note">
            Already have an account?{" "}
            <Link href="/authentication/login">Sign In</Link>
          </p>
        </div>

        <div className="signup-right">
          <div className="visual-card">
            <div className="network-grid" />
            <div className="network-line network-line-1" />
            <div className="network-line network-line-2" />
            <div className="network-line network-line-3" />

            <div className="network-node node-1" />
            <div className="network-node node-2" />
            <div className="network-node node-3" />
            <div className="network-node node-4" />

            <div className="cloud-visual" aria-hidden="true">
              <span className="cloud-puff cloud-puff-1" />
              <span className="cloud-puff cloud-puff-2" />
              <span className="cloud-puff cloud-puff-3" />
              <span className="cloud-base" />
              <span className="cloud-arrow">AWS</span>
            </div>

            <div className="floating-card floating-card-1">
              <span>Account setup</span>
              <strong>Secure</strong>
            </div>

            <div className="floating-card floating-card-2">
              <span>Cloud data</span>
              <strong>Ready</strong>
            </div>

            <div className="floating-card floating-card-3">
              <span>AI guidance</span>
              <strong>Enabled</strong>
            </div>

            <div className="mini-chart" aria-hidden="true">
              <span className="bar bar-1" />
              <span className="bar bar-2" />
              <span className="bar bar-3" />
              <span className="bar bar-4" />
              <span className="bar bar-5" />
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
