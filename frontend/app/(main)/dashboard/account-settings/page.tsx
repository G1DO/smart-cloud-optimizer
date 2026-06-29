"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import "./account-settings.css";
import {
  AwsConnection,
  SessionUser,
  activateConnectedWorkspace,
  getSessionUser,
  toAwsConnection,
  updateSessionUser,
} from "@/app/lib/session";

type TabType = "workspace" | "connections" | "runtime" | "platform";

type RuntimeSettings = {
  forecast_horizon_days: number;
  seasonality_period_days: number;
  minimum_training_days: number;
  confidence_interval: number;
  monthly_budget_cap: number;
  minimum_recommendation_savings: number;
  risk_tolerance: "Conservative" | "Moderate" | "Aggressive";
  allow_spot_recommendations: boolean;
  default_forecasting_model:
    | "Prophet"
    | "SARIMAX"
    | "ETS"
    | "Seasonal Naive"
    | "Naive";
  enable_ensemble_forecasting: boolean;
  collection_interval_hours: number;
  retention_period_days: number;
  api_timeout_seconds: number;
  max_api_retries: number;
  log_level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
};

type ConnectionOut = {
  id: number;
  connection_name: string;
  aws_account_id: string;
  aws_region: string;
  auth_type: string;
  access_verified: boolean;
  access_key_last4: string;
  sync_status: "never" | "success" | "failed" | "in_progress";
  last_sync_at: string | null;
  error_message: string;
  connected_at: string;
  data_user_id: string;
};

type ConnectionTestResult = {
  ok: boolean;
  account_id: string | null;
  error: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

function isDemoUser(candidate: SessionUser | null): boolean {
  return (
    candidate?.userId === "aws-SYNTHETIC-001" ||
    candidate?.awsAccountId === "SYNTHETIC-001" ||
    Boolean(candidate?.email?.toLowerCase().includes("synthetic"))
  );
}

const DEFAULT_SETTINGS: RuntimeSettings = {
  forecast_horizon_days: 30,
  seasonality_period_days: 7,
  minimum_training_days: 30,
  confidence_interval: 0.8,
  monthly_budget_cap: 5000,
  minimum_recommendation_savings: 5,
  risk_tolerance: "Moderate",
  allow_spot_recommendations: false,
  default_forecasting_model: "Prophet",
  enable_ensemble_forecasting: false,
  collection_interval_hours: 24,
  retention_period_days: 365,
  api_timeout_seconds: 30,
  max_api_retries: 3,
  log_level: "INFO",
};

const EMPTY_CONNECTION = {
  connectionName: "",
  awsAccountId: "",
  accessKeyId: "",
  secretAccessKey: "",
  sessionToken: "",
  primaryRegion: "us-east-1",
};

const AWS_REGIONS = [
  "us-east-1",
  "us-east-2",
  "us-west-1",
  "us-west-2",
  "eu-west-1",
  "eu-west-2",
  "eu-central-1",
  "ap-southeast-1",
  "ap-northeast-1",
];

function normalizeTab(tab: string | null): TabType {
  if (tab === "connections" || tab === "runtime" || tab === "platform") {
    return tab;
  }

  return "workspace";
}

export default function AccountSettingsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [activeTab, setActiveTab] = useState<TabType>(
    normalizeTab(searchParams.get("tab")),
  );

  const [user, setUser] = useState<SessionUser | null>(null);

  const [profileName, setProfileName] = useState("");
  const [email, setEmail] = useState("");
  const [image, setImage] = useState("");

  const [connectionForm, setConnectionForm] = useState(EMPTY_CONNECTION);
  const [editingConnectionId, setEditingConnectionId] = useState<string | null>(
    null,
  );

  const [profileSaved, setProfileSaved] = useState(false);
  const [connectionMessage, setConnectionMessage] = useState("");
  const [testingConnection, setTestingConnection] = useState(false);

  const [connections, setConnections] = useState<AwsConnection[]>([]);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [syncAccountId, setSyncAccountId] = useState<string | null>(null);

  const [runtimeSettings, setRuntimeSettings] =
    useState<RuntimeSettings>(DEFAULT_SETTINGS);
  const [settingsEditable, setSettingsEditable] = useState(false);
  const [settingsReason, setSettingsReason] = useState("");
  const [settingsMessage, setSettingsMessage] = useState("");
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [platformMessage, setPlatformMessage] = useState("");

  useEffect(() => {
    setActiveTab(normalizeTab(searchParams.get("tab")));
  }, [searchParams]);

  useEffect(() => {
    syncUser();
    refreshConnections();
  }, []);

  const isDemo =
    user?.userId === "aws-SYNTHETIC-001" ||
    user?.awsAccountId === "SYNTHETIC-001" ||
    user?.email?.toLowerCase().includes("synthetic");

  const hasConnectedAccount = !isDemo && connections.length > 0;

  const userIdValue = isDemo ? "aws-SYNTHETIC-001" : user?.userId || "";
  const awsAccountIdValue = isDemo ? "SYNTHETIC-001" : user?.awsAccountId || "";
  const workspaceRoleValue = isDemo
    ? "Demo Workspace"
    : user?.role || "Workspace";
  const displayEmail = isDemo ? "synthetic-001@demo.opticloud" : email;
  const connectionsCount = isDemo ? 1 : connections.length;

  const profilePreviewName = isDemo
    ? "Synthetic Demo"
    : profileName || user?.profileName || "Workspace User";

  const profilePreviewRole = isDemo
    ? "Demo Workspace"
    : user?.role || "Workspace";

  const runtimeDisabled = isDemo || !settingsEditable || settingsLoading;

  useEffect(() => {
    if (!userIdValue) return;
    loadRuntimeSettings(userIdValue);
  }, [userIdValue, isDemo, hasConnectedAccount]);

  useEffect(() => {
    if (!syncingId || !syncAccountId) return;

    const pollUserId = `aws-${syncAccountId}`;
    let cancelled = false;

    const poll = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/connections?user_id=${encodeURIComponent(pollUserId)}`,
        );

        if (!response.ok || cancelled) return;

        const rows = (await response.json()) as ConnectionOut[];
        if (cancelled) return;

        const mapped = rows.map(toAwsConnection);
        setConnections(mapped);

        const row = mapped.find((item) => item.id === syncingId);
        if (!row) return;

        if (row.syncStatus === "success") {
          setSyncingId(null);
          setSyncAccountId(null);
          setConnectionMessage(
            "Sync complete. Switching to the synced workspace...",
          );
          activateConnectedWorkspace(syncAccountId, mapped);
          router.push("/dashboard/costs");
        } else if (row.syncStatus === "failed") {
          setSyncingId(null);
          setSyncAccountId(null);
          setConnectionMessage(row.errorMessage || "Sync failed.");
        }
      } catch {
        // Transient error — keep polling on the next tick.
      }
    };

    poll();
    const interval = window.setInterval(poll, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [syncingId, syncAccountId, router]);

  function syncUser() {
    const currentUser = getSessionUser();
    setUser(currentUser);
    setProfileName(currentUser?.profileName || "");
    setEmail(currentUser?.email || "");
    setImage(currentUser?.image || "");
  }

  const refreshConnections = async (overrideUserId?: string) => {
    if (typeof window === "undefined") return;

    const currentUser = getSessionUser();
    if (isDemoUser(currentUser)) return;

    const currentUserId = overrideUserId || currentUser.userId;
    if (!currentUserId) return;

    try {
      const response = await fetch(
        `${API_BASE}/api/connections?user_id=${encodeURIComponent(currentUserId)}`,
      );

      if (!response.ok) return;

      const rows = (await response.json()) as ConnectionOut[];
      setConnections(rows.map(toAwsConnection));
    } catch {
      // Backend unreachable — leave the current list in place.
    }
  };

  const goToTab = (tab: TabType) => {
    setActiveTab(tab);
    router.push(`/dashboard/account-settings?tab=${tab}`);
  };

  const loadRuntimeSettings = async (targetUserId: string) => {
    setSettingsLoading(true);
    setSettingsMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/settings?user_id=${encodeURIComponent(targetUserId)}`,
      );

      if (!response.ok) {
        throw new Error("Settings API is not available.");
      }

      const data = await response.json();
      setRuntimeSettings(data.settings || DEFAULT_SETTINGS);
      setSettingsEditable(Boolean(data.editable));
      setSettingsReason(data.reason || "");
    } catch {
      setRuntimeSettings(DEFAULT_SETTINGS);
      setSettingsEditable(!isDemo && hasConnectedAccount);
      setSettingsReason(
        isDemo
          ? "Demo workspace is read-only."
          : hasConnectedAccount
            ? "Using local defaults until the settings API responds."
            : "Connect an AWS account to unlock runtime settings.",
      );
    } finally {
      setSettingsLoading(false);
    }
  };

  const updateRuntimeSetting = <K extends keyof RuntimeSettings>(
    key: K,
    value: RuntimeSettings[K],
  ) => {
    setRuntimeSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
    setSettingsMessage("");
  };

  const saveRuntimeSettings = async () => {
    if (!userIdValue) return;

    setSettingsLoading(true);
    setSettingsMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/settings?user_id=${encodeURIComponent(userIdValue)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(runtimeSettings),
        },
      );

      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw new Error(err?.detail || "Failed to save settings.");
      }

      const data = await response.json();
      setRuntimeSettings(data.settings || runtimeSettings);
      setSettingsEditable(Boolean(data.editable));
      setSettingsReason(data.reason || "");
      setSettingsMessage("Settings saved.");
    } catch (error) {
      setSettingsMessage(
        error instanceof Error ? error.message : "Failed to save settings.",
      );
    } finally {
      setSettingsLoading(false);
    }
  };

  const resetRuntimeSettings = async () => {
    if (!userIdValue) return;

    setSettingsLoading(true);
    setSettingsMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/settings/reset?user_id=${encodeURIComponent(userIdValue)}`,
        { method: "POST" },
      );

      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw new Error(err?.detail || "Failed to reset settings.");
      }

      const data = await response.json();
      setRuntimeSettings(data.settings || DEFAULT_SETTINGS);
      setSettingsMessage("Defaults restored.");
    } catch {
      setRuntimeSettings(DEFAULT_SETTINGS);
      setSettingsMessage("Defaults restored locally.");
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleSaveProfile = () => {
    updateSessionUser({
      profileName,
      email,
      image,
    });

    syncUser();
    setProfileSaved(true);
    window.setTimeout(() => setProfileSaved(false), 2200);
  };

  const handleConnectionField = (
    field: keyof typeof EMPTY_CONNECTION,
    value: string,
  ) => {
    setConnectionForm((prev) => ({
      ...prev,
      [field]: value,
    }));
    setConnectionMessage("");
  };

  const handleTestConnection = async () => {
    if (isDemo) return;

    if (!connectionForm.accessKeyId || !connectionForm.secretAccessKey) {
      setConnectionMessage(
        "AWS Access Key ID and Secret Access Key are required.",
      );
      return;
    }

    setTestingConnection(true);
    setConnectionMessage("");

    try {
      const response = await fetch(`${API_BASE}/api/connections/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          aws_access_key_id: connectionForm.accessKeyId,
          aws_secret_access_key: connectionForm.secretAccessKey,
          aws_session_token: connectionForm.sessionToken,
          aws_region: connectionForm.primaryRegion,
        }),
      });

      const body = (await response
        .json()
        .catch(() => null)) as ConnectionTestResult | null;

      if (!response.ok || !body) {
        setConnectionMessage(body?.error || "Connection test failed.");
        return;
      }

      if (body.ok) {
        const detectedAccountId = body.account_id;
        if (detectedAccountId) {
          setConnectionForm((prev) => ({
            ...prev,
            awsAccountId: detectedAccountId,
          }));
        }
        setConnectionMessage(
          `Connection verified — account ${detectedAccountId ?? "detected"}.`,
        );
      } else {
        setConnectionMessage(body.error || "Connection test failed.");
      }
    } catch {
      setConnectionMessage("Connection test failed.");
    } finally {
      setTestingConnection(false);
    }
  };

  const resetConnectionForm = () => {
    setConnectionForm(EMPTY_CONNECTION);
    setEditingConnectionId(null);
    setConnectionMessage("");
  };

  const handleAddOrUpdateConnection = async () => {
    if (isDemo) return;

    if (!connectionForm.accessKeyId || !connectionForm.secretAccessKey) {
      setConnectionMessage(
        "AWS Access Key ID and Secret Access Key are required.",
      );
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/connections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          connection_name: connectionForm.connectionName.trim(),
          aws_access_key_id: connectionForm.accessKeyId,
          aws_secret_access_key: connectionForm.secretAccessKey,
          aws_session_token: connectionForm.sessionToken,
          aws_region: connectionForm.primaryRegion,
          aws_account_id: connectionForm.awsAccountId.trim() || undefined,
        }),
      });

      if (response.status === 409) {
        setConnectionMessage("This AWS account is already connected.");
        return;
      }

      if (!response.ok) {
        const err = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        setConnectionMessage(err?.detail || "Failed to add connection.");
        return;
      }

      const row = (await response.json()) as ConnectionOut;
      const savedConn = toAwsConnection(row);

      const nextConnections = connections.some(
        (item) => item.id === savedConn.id,
      )
        ? connections.map((item) =>
            item.id === savedConn.id ? savedConn : item,
          )
        : [...connections, savedConn];

      setConnections(nextConnections);

      // Switch the active workspace at save time. The connection is self-owned
      // under `aws-<accountId>`, but the session id right after login is the
      // login id — a list query keyed by it returns nothing after navigation.
      // Activating here makes the session id `aws-<accountId>` immediately so the
      // list query matches and the Sync button survives navigation/reload. Use
      // the account id from the saved response (the form's may be blank since it
      // is auto-detected).
      activateConnectedWorkspace(savedConn.awsAccountId, nextConnections);

      await refreshConnections(`aws-${savedConn.awsAccountId}`);
      resetConnectionForm();
      setConnectionMessage("Connection added.");
    } catch {
      setConnectionMessage("Failed to add connection.");
    }
  };

  const handleEditConnection = (connection: AwsConnection) => {
    setEditingConnectionId(connection.id);
    setConnectionForm({
      connectionName: connection.connectionName,
      awsAccountId: connection.awsAccountId,
      accessKeyId: "",
      secretAccessKey: "",
      sessionToken: "",
      primaryRegion: connection.primaryRegion,
    });
    setConnectionMessage("");
    goToTab("connections");
  };

  const handleDeleteConnection = async (connection: AwsConnection) => {
    if (isDemo) return;

    try {
      const response = await fetch(
        `${API_BASE}/api/connections/${connection.id}?user_id=${encodeURIComponent(
          `aws-${connection.awsAccountId}`,
        )}`,
        { method: "DELETE" },
      );

      if (!response.ok && response.status !== 404) {
        setConnectionMessage("Failed to remove connection.");
        return;
      }

      if (editingConnectionId === connection.id) {
        resetConnectionForm();
      }

      setConnections((prev) =>
        prev.filter((item) => item.id !== connection.id),
      );
      await refreshConnections();
    } catch {
      setConnectionMessage("Failed to remove connection.");
    }
  };

  const handleSyncConnection = async (connection: AwsConnection) => {
    if (isDemo) return;

    const confirmed = window.confirm(
      "Syncing replaces any existing data for this account. Continue?",
    );
    if (!confirmed) return;

    const pollUserId = `aws-${connection.awsAccountId}`;
    setConnectionMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/connections/${connection.id}/sync?user_id=${encodeURIComponent(
          pollUserId,
        )}`,
        { method: "POST" },
      );

      if (response.status === 409) {
        setConnectionMessage("A sync is already running for this account.");
        return;
      }

      if (!response.ok) {
        const err = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        setConnectionMessage(err?.detail || "Failed to start sync.");
        return;
      }

      setSyncingId(connection.id);
      setSyncAccountId(connection.awsAccountId);
      setConnectionMessage("Sync started. Collecting AWS data...");
    } catch {
      setConnectionMessage("Failed to start sync.");
    }
  };

  const handleClearCache = () => {
    if (typeof window === "undefined") return;

    window.sessionStorage.clear();
    setPlatformMessage("Cache cleared.");
    window.setTimeout(() => setPlatformMessage(""), 2200);
  };

  const renderAwsConnectionForm = (disabled = false) => (
    <section className="account-settings-card aws-connections-card">
      <div className="settings-card-header-row">
        <h2>Add AWS Account</h2>
        {disabled ? <span className="settings-chip">Preview</span> : null}
      </div>

      <div
        className={
          disabled
            ? "aws-connections-panel disabled-preview"
            : "aws-connections-panel"
        }
      >
        <div className="aws-connections-panel-title">
          <span className="aws-connections-chevron">▾</span>
          Access Keys Connection
        </div>

        <div className="aws-connections-form">
          <div className="aws-connections-grid">
            <label className="account-settings-field">
              <span>Connection Name</span>
              <input
                disabled={disabled}
                value={disabled ? "Production" : connectionForm.connectionName}
                onChange={(e) =>
                  handleConnectionField("connectionName", e.target.value)
                }
                placeholder="Production"
              />
            </label>

            <label className="account-settings-field">
              <span>AWS Access Key ID</span>
              <input
                disabled={disabled}
                value={
                  disabled
                    ? "AKIAIOSFODNN7EXAMPLE"
                    : connectionForm.accessKeyId
                }
                onChange={(e) =>
                  handleConnectionField("accessKeyId", e.target.value)
                }
                placeholder="AKIAIOSFODNN7EXAMPLE"
              />
            </label>

            <label className="account-settings-field">
              <span>AWS Secret Access Key</span>
              <input
                type="password"
                autoComplete="off"
                disabled={disabled}
                value={disabled ? "secret" : connectionForm.secretAccessKey}
                onChange={(e) =>
                  handleConnectionField("secretAccessKey", e.target.value)
                }
                placeholder="Secret access key"
              />
            </label>

            <label className="account-settings-field">
              <span>AWS Session Token (optional)</span>
              <input
                type="password"
                autoComplete="off"
                disabled={disabled}
                value={disabled ? "" : connectionForm.sessionToken}
                onChange={(e) =>
                  handleConnectionField("sessionToken", e.target.value)
                }
                placeholder="Only for temporary STS credentials"
              />
            </label>

            <label className="account-settings-field">
              <span>AWS Account ID (optional — auto-detected)</span>
              <input
                disabled={disabled}
                value={disabled ? "123456789012" : connectionForm.awsAccountId}
                onChange={(e) =>
                  handleConnectionField("awsAccountId", e.target.value)
                }
                placeholder="Auto-detected from keys"
              />
            </label>

            <label className="account-settings-field full-width">
              <span>Primary Region</span>
              <select
                className="account-settings-select"
                disabled={disabled}
                value={disabled ? "us-east-1" : connectionForm.primaryRegion}
                onChange={(e) =>
                  handleConnectionField("primaryRegion", e.target.value)
                }
              >
                {AWS_REGIONS.map((region) => (
                  <option key={region} value={region}>
                    {region}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="settings-action-row">
            <button
              type="button"
              className="settings-btn secondary"
              onClick={handleTestConnection}
              disabled={disabled || testingConnection}
            >
              {testingConnection ? "Testing..." : "Test Connection"}
            </button>

            <div className="settings-action-row right">
              {editingConnectionId && !disabled ? (
                <button
                  type="button"
                  className="settings-btn secondary"
                  onClick={resetConnectionForm}
                >
                  Cancel
                </button>
              ) : null}

              <button
                type="button"
                className="settings-btn primary"
                onClick={handleAddOrUpdateConnection}
                disabled={disabled}
              >
                {editingConnectionId ? "Update Account" : "Add Account"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {connectionMessage && !disabled ? (
        <div
          className={`settings-inline-message ${
            connectionMessage.toLowerCase().includes("verified") ||
            connectionMessage.toLowerCase().includes("passed") ||
            connectionMessage.toLowerCase().includes("added") ||
            connectionMessage.toLowerCase().includes("updated")
              ? "success"
              : ""
          }`}
        >
          {connectionMessage}
        </div>
      ) : null}
    </section>
  );

  const renderWorkspace = () => (
    <>
      <div className="account-settings-grid">
        <section className="account-settings-card">
          <div className="account-settings-card-head">
            <h2>Workspace Profile</h2>
          </div>

          <div className="account-settings-form-grid">
            <label className="account-settings-field">
              <span>Profile Name</span>
              <input
                value={profileName || profilePreviewName}
                onChange={(e) => setProfileName(e.target.value)}
                readOnly={isDemo}
              />
            </label>

            <label className="account-settings-field">
              <span>Email Address</span>
              <input
                value={displayEmail}
                onChange={(e) => setEmail(e.target.value)}
                readOnly={isDemo}
              />
            </label>

            <label className="account-settings-field full-width">
              <span>Profile Image URL</span>
              <input
                value={image}
                onChange={(e) => setImage(e.target.value)}
                placeholder="Paste image URL"
                readOnly={isDemo}
              />
            </label>
          </div>

          <div className="settings-card-footer">
            {profileSaved ? (
              <span className="settings-inline-message success">
                Profile saved.
              </span>
            ) : (
              <span />
            )}

            <button
              type="button"
              className="settings-btn primary"
              onClick={handleSaveProfile}
              disabled={isDemo}
            >
              Save Profile
            </button>
          </div>
        </section>

        <section className="account-settings-card">
          <div className="account-settings-card-head">
            <h2>Workspace Details</h2>
          </div>

          <div className="account-settings-form-grid">
            <label className="account-settings-field">
              <span>User ID</span>
              <input value={userIdValue} readOnly />
            </label>

            <label className="account-settings-field">
              <span>AWS Account ID</span>
              <input value={awsAccountIdValue} readOnly />
            </label>

            <label className="account-settings-field full-width">
              <span>Workspace Role</span>
              <input value={workspaceRoleValue} readOnly />
            </label>
          </div>
        </section>
      </div>

      <section className="account-settings-card">
        <div className="account-settings-card-head">
          <h2>System Status</h2>
        </div>

        <div className="account-settings-metrics">
          <div className="account-settings-metric">
            <span>Mode</span>
            <strong>{isDemo ? "Demo" : "Live"}</strong>
          </div>

          <div className="account-settings-metric">
            <span>AWS Region</span>
            <strong>us-east-1</strong>
          </div>

          <div className="account-settings-metric">
            <span>Database</span>
            <strong>SQLite</strong>
          </div>

          <div className="account-settings-metric">
            <span>Accounts</span>
            <strong>{connectionsCount}</strong>
          </div>
        </div>
      </section>
    </>
  );

  const renderConnections = () => (
    <>
      <section className="account-settings-card aws-connections-card">
        <div className="settings-card-header-row">
          <h2>AWS Account Connections</h2>
          {isDemo ? <span className="settings-chip success">Demo Source</span> : null}
        </div>

        {isDemo ? (
          <div className="aws-connections-table-wrap">
            <table className="aws-connections-table">
              <thead>
                <tr>
                  <th>Connection</th>
                  <th>AWS Account ID</th>
                  <th>Region</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                <tr>
                  <td>Synthetic Demo</td>
                  <td>SYNTHETIC-001</td>
                  <td>us-east-1</td>
                  <td>
                    <span className="aws-status-badge connected">Connected</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : connections.length === 0 ? (
          <div className="aws-empty-state">No AWS accounts connected yet.</div>
        ) : (
          <div className="aws-connections-table-wrap">
            <table className="aws-connections-table">
              <thead>
                <tr>
                  <th>Connection</th>
                  <th>AWS Account ID</th>
                  <th>Access Key</th>
                  <th>Region</th>
                  <th>Status</th>
                  <th>Sync Status</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {connections.map((connection) => (
                  <tr key={connection.id}>
                    <td>{connection.connectionName}</td>
                    <td>{connection.awsAccountId}</td>
                    <td className="aws-role-cell">{`••••${connection.accessKeyLast4 ?? ""}`}</td>
                    <td>{connection.primaryRegion}</td>
                    <td>
                      <span
                        className={`aws-status-badge ${
                          connection.status === "Connected"
                            ? "connected"
                            : connection.status === "Failed"
                              ? "failed"
                              : "not-tested"
                        }`}
                      >
                        {connection.status}
                      </span>
                    </td>
                    <td>
                      {connection.syncStatus === "in_progress" ||
                      syncingId === connection.id ? (
                        <span className="aws-status-badge not-tested">
                          Syncing...
                        </span>
                      ) : connection.syncStatus === "success" ? (
                        <span className="aws-status-badge connected">
                          Synced
                          {connection.lastSyncAt
                            ? ` · ${new Date(
                                connection.lastSyncAt,
                              ).toLocaleString()}`
                            : ""}
                        </span>
                      ) : connection.syncStatus === "failed" ? (
                        <span
                          className="aws-status-badge failed"
                          title={connection.errorMessage || ""}
                        >
                          Failed
                        </span>
                      ) : (
                        <span className="aws-status-badge not-tested">
                          Never
                        </span>
                      )}
                    </td>
                    <td>
                      <div className="aws-table-actions">
                        <button
                          type="button"
                          className="settings-mini-btn"
                          onClick={() => handleSyncConnection(connection)}
                          disabled={
                            syncingId === connection.id ||
                            connection.syncStatus === "in_progress"
                          }
                        >
                          {syncingId === connection.id ? "Syncing..." : "Sync"}
                        </button>

                        <button
                          type="button"
                          className="settings-mini-btn"
                          onClick={() => handleEditConnection(connection)}
                        >
                          Edit
                        </button>

                        <button
                          type="button"
                          className="settings-mini-btn danger"
                          onClick={() => handleDeleteConnection(connection)}
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {renderAwsConnectionForm(isDemo)}
    </>
  );

  const renderRuntime = () => (
    <>
      <section className="account-settings-card">
        <div className="account-settings-card-head">
          <h2>Forecast Configuration</h2>
        </div>

        <div className="account-settings-form-grid">
          <label className="account-settings-field">
            <span>Forecast Horizon (Days)</span>
            <input
              type="number"
              min={7}
              max={180}
              value={runtimeSettings.forecast_horizon_days}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "forecast_horizon_days",
                  Number(e.target.value),
                )
              }
            />
          </label>

          <label className="account-settings-field">
            <span>Seasonality Period (Days)</span>
            <input
              type="number"
              min={1}
              max={30}
              value={runtimeSettings.seasonality_period_days}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "seasonality_period_days",
                  Number(e.target.value),
                )
              }
            />
          </label>

          <label className="account-settings-field">
            <span>Minimum Training Days</span>
            <input
              type="number"
              min={14}
              max={365}
              value={runtimeSettings.minimum_training_days}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "minimum_training_days",
                  Number(e.target.value),
                )
              }
            />
          </label>

          <label className="account-settings-field">
            <span>Confidence Interval</span>
            <input
              type="number"
              min={0.5}
              max={0.99}
              step={0.05}
              value={runtimeSettings.confidence_interval}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "confidence_interval",
                  Number(e.target.value),
                )
              }
            />
          </label>
        </div>
      </section>

      <section className="account-settings-card">
        <div className="account-settings-card-head">
          <h2>Optimization Configuration</h2>
        </div>

        <div className="account-settings-form-grid">
          <label className="account-settings-field">
            <span>Monthly Budget Cap ($)</span>
            <input
              type="number"
              min={0}
              max={100000}
              step={100}
              value={runtimeSettings.monthly_budget_cap}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting("monthly_budget_cap", Number(e.target.value))
              }
            />
          </label>

          <label className="account-settings-field">
            <span>Minimum Savings ($/month)</span>
            <input
              type="number"
              min={0}
              max={1000}
              step={5}
              value={runtimeSettings.minimum_recommendation_savings}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "minimum_recommendation_savings",
                  Number(e.target.value),
                )
              }
            />
          </label>

          <label className="account-settings-field">
            <span>Risk Tolerance</span>
            <select
              className="account-settings-select"
              value={runtimeSettings.risk_tolerance}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "risk_tolerance",
                  e.target.value as RuntimeSettings["risk_tolerance"],
                )
              }
            >
              <option>Conservative</option>
              <option>Moderate</option>
              <option>Aggressive</option>
            </select>
          </label>

          <label className="account-settings-field">
            <span>Allow Spot Recommendations</span>
            <select
              className="account-settings-select"
              value={runtimeSettings.allow_spot_recommendations ? "true" : "false"}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "allow_spot_recommendations",
                  e.target.value === "true",
                )
              }
            >
              <option value="false">Disabled</option>
              <option value="true">Enabled</option>
            </select>
          </label>
        </div>
      </section>

      <section className="account-settings-card">
        <div className="account-settings-card-head">
          <h2>ML Model Configuration</h2>
        </div>

        <div className="account-settings-form-grid">
          <label className="account-settings-field">
            <span>Default Forecasting Model</span>
            <select
              className="account-settings-select"
              value={runtimeSettings.default_forecasting_model}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "default_forecasting_model",
                  e.target
                    .value as RuntimeSettings["default_forecasting_model"],
                )
              }
            >
              <option>Prophet</option>
              <option>SARIMAX</option>
              <option>ETS</option>
              <option>Seasonal Naive</option>
              <option>Naive</option>
            </select>
          </label>

          <label className="account-settings-field">
            <span>Enable Ensemble Forecasting</span>
            <select
              className="account-settings-select"
              value={runtimeSettings.enable_ensemble_forecasting ? "true" : "false"}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "enable_ensemble_forecasting",
                  e.target.value === "true",
                )
              }
            >
              <option value="false">Disabled</option>
              <option value="true">Enabled</option>
            </select>
          </label>
        </div>

        <div className="settings-card-footer">
          <span
            className={`settings-inline-message ${
              settingsMessage ? "success" : ""
            }`}
          >
            {settingsMessage || settingsReason}
          </span>

          <div className="settings-action-row right">
            <button
              type="button"
              className="settings-btn secondary"
              onClick={resetRuntimeSettings}
              disabled={runtimeDisabled}
            >
              Reset
            </button>

            <button
              type="button"
              className="settings-btn primary"
              onClick={saveRuntimeSettings}
              disabled={runtimeDisabled}
            >
              {settingsLoading ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </section>
    </>
  );

  const renderPlatform = () => (
    <>
      <section className="account-settings-card">
        <div className="account-settings-card-head">
          <h2>Advanced Settings</h2>
        </div>

        <div className="account-settings-form-grid">
          <label className="account-settings-field">
            <span>Collection Interval (Hours)</span>
            <input
              type="number"
              min={1}
              max={168}
              value={runtimeSettings.collection_interval_hours}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "collection_interval_hours",
                  Number(e.target.value),
                )
              }
            />
          </label>

          <label className="account-settings-field">
            <span>Retention Period (Days)</span>
            <input
              type="number"
              min={30}
              max={730}
              value={runtimeSettings.retention_period_days}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "retention_period_days",
                  Number(e.target.value),
                )
              }
            />
          </label>

          <label className="account-settings-field">
            <span>API Timeout (Seconds)</span>
            <input
              type="number"
              min={10}
              max={300}
              value={runtimeSettings.api_timeout_seconds}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "api_timeout_seconds",
                  Number(e.target.value),
                )
              }
            />
          </label>

          <label className="account-settings-field">
            <span>Max API Retries</span>
            <input
              type="number"
              min={1}
              max={10}
              value={runtimeSettings.max_api_retries}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting("max_api_retries", Number(e.target.value))
              }
            />
          </label>

          <label className="account-settings-field full-width">
            <span>Log Level</span>
            <select
              className="account-settings-select"
              value={runtimeSettings.log_level}
              disabled={runtimeDisabled}
              onChange={(e) =>
                updateRuntimeSetting(
                  "log_level",
                  e.target.value as RuntimeSettings["log_level"],
                )
              }
            >
              <option>DEBUG</option>
              <option>INFO</option>
              <option>WARNING</option>
              <option>ERROR</option>
            </select>
          </label>
        </div>

        <div className="settings-card-footer">
          <span
            className={`settings-inline-message ${
              platformMessage || settingsMessage ? "success" : ""
            }`}
          >
            {platformMessage || settingsMessage || "Ready"}
          </span>

          <div className="settings-action-row right">
            <button
              type="button"
              className="settings-btn secondary"
              onClick={handleClearCache}
            >
              Clear Cache
            </button>

            <button
              type="button"
              className="settings-btn secondary"
              onClick={resetRuntimeSettings}
              disabled={runtimeDisabled}
            >
              Reset
            </button>

            <button
              type="button"
              className="settings-btn primary"
              onClick={saveRuntimeSettings}
              disabled={runtimeDisabled}
            >
              Save
            </button>
          </div>
        </div>
      </section>
    </>
  );

  return (
    <div className="account-settings-page">
      <div className="account-settings-shell">
        <section className="account-settings-hero">
          <div className="account-settings-hero-copy">
            <p className="account-settings-eyebrow">DevOps Control Center</p>
            <h1>Cloud workspace settings</h1>
            <h2>access, runtime, operations</h2>
          </div>

          <div className="account-settings-hero-badge">
            <div className="account-settings-badge-top">
              <div className="account-settings-avatar">
                {image && !isDemo ? (
                  <img
                    src={image}
                    alt={profilePreviewName}
                    className="account-settings-avatar-image"
                  />
                ) : (
                  <img
                    src="/icons/sidebar/profile.png"
                    alt="profile"
                    className="account-settings-fallback-icon"
                  />
                )}
              </div>

              <div className="account-settings-badge-copy">
                <strong>{profilePreviewName}</strong>
                <span>{profilePreviewRole}</span>
              </div>
            </div>

            <div className="account-settings-badge-meta">
              <div className="account-settings-meta-pill">
                <div className="account-settings-meta-pill-label">Mode</div>
                <div className="account-settings-meta-pill-value">
                  {isDemo ? "Demo" : "Live"}
                </div>
              </div>

              <div className="account-settings-meta-pill">
                <div className="account-settings-meta-pill-label">Accounts</div>
                <div className="account-settings-meta-pill-value">
                  {connectionsCount} Account{connectionsCount === 1 ? "" : "s"}
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="account-settings-tabs">
          <button
            type="button"
            className={`account-settings-tab ${
              activeTab === "workspace" ? "active" : ""
            }`}
            onClick={() => goToTab("workspace")}
          >
            Workspace
          </button>

          <button
            type="button"
            className={`account-settings-tab ${
              activeTab === "connections" ? "active" : ""
            }`}
            onClick={() => goToTab("connections")}
          >
            AWS Connections
          </button>

          <button
            type="button"
            className={`account-settings-tab ${
              activeTab === "runtime" ? "active" : ""
            }`}
            onClick={() => goToTab("runtime")}
          >
            Runtime Config
          </button>

          <button
            type="button"
            className={`account-settings-tab ${
              activeTab === "platform" ? "active" : ""
            }`}
            onClick={() => goToTab("platform")}
          >
            Platform Controls
          </button>
        </div>

        {activeTab === "workspace" ? renderWorkspace() : null}
        {activeTab === "connections" ? renderConnections() : null}
        {activeTab === "runtime" ? renderRuntime() : null}
        {activeTab === "platform" ? renderPlatform() : null}
      </div>
    </div>
  );
}
