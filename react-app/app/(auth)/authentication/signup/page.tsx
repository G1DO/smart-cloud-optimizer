"use client";

import "./signup.css";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

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

  async function handleSignup(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setSuccessMessage("");

    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/auth/signup`, {
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
          src="/icons/logo.png"
          alt="OptiCloud logo"
          width={90}
          height={90}
          className="auth-top-logo-img"
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
              />
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
          <div className="visual-card" />
        </div>
      </section>
    </main>
  );
}