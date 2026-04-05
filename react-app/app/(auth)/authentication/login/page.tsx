"use client";

import "./login.css";
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

function persistAuth(data: AuthResponse) {
  if (typeof window === "undefined") return;

  localStorage.setItem("isLoggedIn", "true");
  localStorage.setItem("auth_user_id", data.user_id ?? "");
  localStorage.setItem("auth_email", data.email ?? "");
  localStorage.setItem("auth_display_name", data.profile_name ?? "");
  localStorage.setItem("demo_mode", data.demo_mode ? "true" : "false");

  if (data.selected_user) {
    localStorage.setItem("selected_user", data.selected_user);
  } else {
    localStorage.removeItem("selected_user");
  }
}

async function readJsonSafe(response: Response) {
  const text = await response.text();

  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { detail: text || "Invalid server response." };
  }
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);

  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const isDisabled = useMemo(
    () => loading || demoLoading,
    [loading, demoLoading]
  );

  useEffect(() => {
    const remembered = localStorage.getItem("remember_email");
    if (remembered) {
      setEmail(remembered);
      setRememberMe(true);
    }
  }, []);

  async function handleLogin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setSuccessMessage("");

    if (!email.trim() || !password.trim()) {
      setError("Please enter both email and password.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        cache: "no-store",
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      const data = await readJsonSafe(response);

      if (!response.ok) {
        throw new Error(data.detail || data.message || "Login failed.");
      }

      persistAuth(data);

      if (rememberMe) {
        localStorage.setItem("remember_email", email.trim());
      } else {
        localStorage.removeItem("remember_email");
      }

      setSuccessMessage(data.message || "Login successful.");
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
      const response = await fetch(`${API_BASE}/api/auth/demo`, {
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
    <main className="login-page">
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
          src="/icons/logo.png"
          alt="OptiCloud logo"
          width={90}
          height={90}
          className="auth-top-logo-img"
          priority
        />
      </Link>

      <section className="login-shell">
        <div className="login-left glass-card">
          <div className="brand-wrap">
            <h1 className="login-title">Welcome Back</h1>
            <p className="login-subtitle">
              Log in to continue monitoring usage and optimizing cloud costs
            </p>
          </div>

          <form className="login-form" onSubmit={handleLogin}>
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
                autoComplete="current-password"
              />
            </div>

            <div className="form-row">
              <label className="remember-me">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  disabled={isDisabled}
                />
                <span>Remember me</span>
              </label>

              <button type="button" className="forgot-link" disabled>
                Forgot password?
              </button>
            </div>

            {error ? <div className="auth-message auth-error">{error}</div> : null}
            {successMessage ? (
              <div className="auth-message auth-success">{successMessage}</div>
            ) : null}

            <button type="submit" className="primary-btn" disabled={isDisabled}>
              {loading ? "Signing In..." : "Sign In"}
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
            Don&apos;t have an account?{" "}
            <Link href="/authentication/signup">Create one</Link>
          </p>
        </div>

        <div className="login-right">
          <div className="visual-card" />
        </div>
      </section>
    </main>
  );
}