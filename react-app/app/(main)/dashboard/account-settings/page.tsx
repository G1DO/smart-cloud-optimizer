"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import "./account-settings.css";
import {
    AwsConnection,
    SessionUser,
    deleteAwsConnection,
    getSessionUser,
    updateSessionUser,
    upsertAwsConnection,
} from "@/app/lib/session";

type TabType = "profile" | "connections";

const EMPTY_CONNECTION: Omit<AwsConnection, "id" | "status"> = {
    connectionName: "",
    awsAccountId: "",
    iamRoleArn: "",
    externalId: "",
    primaryRegion: "us-east-1",
};

export default function AccountSettingsPage() {
    const router = useRouter();
    const searchParams = useSearchParams();

    const initialTab = (
        searchParams.get("tab") === "connections" ? "connections" : "profile"
    ) as TabType;

    const [activeTab, setActiveTab] = useState<TabType>(initialTab);
    const [user, setUser] = useState<SessionUser | null>(null);

    const [profileName, setProfileName] = useState("");
    const [email, setEmail] = useState("");
    const [image, setImage] = useState("");

    const [connectionForm, setConnectionForm] = useState(EMPTY_CONNECTION);
    const [editingConnectionId, setEditingConnectionId] = useState<string | null>(null);

    const [profileSaved, setProfileSaved] = useState(false);
    const [connectionMessage, setConnectionMessage] = useState("");
    const [testingConnection, setTestingConnection] = useState(false);

    useEffect(() => {
        const tab = searchParams.get("tab") === "connections" ? "connections" : "profile";
        setActiveTab(tab);
    }, [searchParams]);

    useEffect(() => {
        const currentUser = getSessionUser();
        setUser(currentUser);
        setProfileName(currentUser.profileName || "");
        setEmail(currentUser.email || "");
        setImage(currentUser.image || "");
    }, []);

    const connections = useMemo(() => user?.awsConnections || [], [user]);

    const syncUser = () => {
        const currentUser = getSessionUser();
        setUser(currentUser);
        setProfileName(currentUser.profileName || "");
        setEmail(currentUser.email || "");
        setImage(currentUser.image || "");
    };

    const goToTab = (tab: TabType) => {
        setActiveTab(tab);
        router.push(`/dashboard/account-settings?tab=${tab}`);
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

    const handleConnectionField = (field: keyof typeof EMPTY_CONNECTION, value: string) => {
        setConnectionForm((prev) => ({
            ...prev,
            [field]: value,
        }));
        setConnectionMessage("");
    };

    const handleTestConnection = () => {
        setTestingConnection(true);
        setConnectionMessage("");

        window.setTimeout(() => {
            setTestingConnection(false);

            if (
                !connectionForm.connectionName ||
                !connectionForm.awsAccountId ||
                !connectionForm.iamRoleArn
            ) {
                setConnectionMessage(
                    "Please fill connection name, AWS account ID, and IAM role ARN first."
                );
                return;
            }

            setConnectionMessage("Connection test passed successfully.");
        }, 900);
    };

    const resetConnectionForm = () => {
        setConnectionForm(EMPTY_CONNECTION);
        setEditingConnectionId(null);
        setConnectionMessage("");
    };

    const handleAddOrUpdateConnection = () => {
        if (
            !connectionForm.connectionName ||
            !connectionForm.awsAccountId ||
            !connectionForm.iamRoleArn
        ) {
            setConnectionMessage("Please complete all required AWS connection fields.");
            return;
        }

        const connection: AwsConnection = {
            id: editingConnectionId || `conn-${Date.now()}`,
            connectionName: connectionForm.connectionName.trim(),
            awsAccountId: connectionForm.awsAccountId.trim(),
            iamRoleArn: connectionForm.iamRoleArn.trim(),
            externalId: connectionForm.externalId.trim(),
            primaryRegion: connectionForm.primaryRegion,
            status: "Connected",
        };

        upsertAwsConnection(connection);
        syncUser();
        resetConnectionForm();
        setConnectionMessage(
            editingConnectionId ? "Connection updated successfully." : "Connection added successfully."
        );
    };

    const handleEditConnection = (connection: AwsConnection) => {
        setActiveTab("connections");
        router.push("/dashboard/account-settings?tab=connections");
        setEditingConnectionId(connection.id);
        setConnectionForm({
            connectionName: connection.connectionName,
            awsAccountId: connection.awsAccountId,
            iamRoleArn: connection.iamRoleArn,
            externalId: connection.externalId,
            primaryRegion: connection.primaryRegion,
        });
        setConnectionMessage("");
    };

    const handleDeleteConnection = (id: string) => {
        deleteAwsConnection(id);
        syncUser();
        if (editingConnectionId === id) {
            resetConnectionForm();
        }
    };

    const profilePreviewName = profileName || user?.profileName || "synthetic-001";
    const profilePreviewRole = user?.role || "Demo Workspace";
    const userIdValue = user?.userId || "";
    const awsAccountIdValue = user?.awsAccountId || "";
    const workspaceRoleValue = user?.role || "";
    const connectionsCount = connections.length;

    return (
        <div className="account-settings-page">
            <div className="account-settings-shell">
                <section className="account-settings-hero">
                    <div className="account-settings-hero-copy">
                        <p className="account-settings-eyebrow">Control Center</p>
                        <h1>Manage your workspace profile</h1>
                        <h2>and AWS connection setup clearly</h2>
                        <span>
                            Update the identity shown across the dashboard, keep workspace data organized,
                            and manage AWS account connections with a cleaner setup flow that matches the
                            rest of your pages.
                        </span>
                    </div>

                    <div className="account-settings-hero-badge">
                        <div className="account-settings-badge-top">
                            <div className="account-settings-avatar">
                                {image ? (
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
                                <div className="account-settings-meta-pill-label">Workspace</div>
                                <div className="account-settings-meta-pill-value">
                                    {workspaceRoleValue || "Demo Workspace"}
                                </div>
                            </div>

                            <div className="account-settings-meta-pill">
                                <div className="account-settings-meta-pill-label">Connected Accounts</div>
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
                        className={`account-settings-tab ${activeTab === "profile" ? "active" : ""}`}
                        onClick={() => goToTab("profile")}
                    >
                        Account Settings
                    </button>

                    <button
                        type="button"
                        className={`account-settings-tab ${activeTab === "connections" ? "active" : ""}`}
                        onClick={() => goToTab("connections")}
                    >
                        Manage AWS Connections
                    </button>
                </div>

                {activeTab === "profile" && (
                    <>
                        <div className="account-settings-grid">
                            <section className="account-settings-card">
                                <div className="account-settings-card-head">
                                    <h2>Basic Information</h2>
                                    <p>Edit the details visible across the dashboard UI</p>
                                </div>

                                <div className="account-settings-form-grid">
                                    <label className="account-settings-field">
                                        <span>Profile Name</span>
                                        <input
                                            type="text"
                                            value={profileName}
                                            onChange={(e) => {
                                                setProfileName(e.target.value);
                                                setProfileSaved(false);
                                            }}
                                            placeholder="Enter profile name"
                                        />
                                    </label>

                                    <label className="account-settings-field">
                                        <span>Email Address</span>
                                        <input
                                            type="email"
                                            value={email}
                                            onChange={(e) => {
                                                setEmail(e.target.value);
                                                setProfileSaved(false);
                                            }}
                                            placeholder="Enter email address"
                                        />
                                    </label>

                                    <label className="account-settings-field full-width">
                                        <span>Profile Image URL</span>
                                        <input
                                            type="text"
                                            value={image}
                                            onChange={(e) => {
                                                setImage(e.target.value);
                                                setProfileSaved(false);
                                            }}
                                            placeholder="Paste image URL"
                                        />
                                    </label>
                                </div>
                            </section>

                            <section className="account-settings-card">
                                <div className="account-settings-card-head">
                                    <h2>Workspace Details</h2>
                                    <p>Read-only account information for the current workspace</p>
                                </div>

                                <div className="account-settings-form-grid">
                                    <label className="account-settings-field">
                                        <span>User ID</span>
                                        <input type="text" value={userIdValue} readOnly />
                                    </label>

                                    <label className="account-settings-field">
                                        <span>AWS Account ID</span>
                                        <input type="text" value={awsAccountIdValue} readOnly />
                                    </label>

                                    <label className="account-settings-field full-width">
                                        <span>Workspace Role</span>
                                        <input type="text" value={workspaceRoleValue} readOnly />
                                    </label>
                                </div>
                            </section>
                        </div>

                        <section className="account-settings-card account-settings-actions-card">
                            <div className="account-settings-card-head">
                                <h2>Save Changes</h2>
                                <p>Your updates will appear in the sidebar, top bar, and profile dropdown</p>
                            </div>

                            <div className="account-settings-actions">
                                <button
                                    type="button"
                                    className="account-settings-save-btn"
                                    onClick={handleSaveProfile}
                                >
                                    Save Changes
                                </button>

                                {profileSaved && (
                                    <span className="account-settings-saved-state">Saved successfully.</span>
                                )}
                            </div>
                        </section>
                    </>
                )}

                {activeTab === "connections" && (
                    <>
                        <section className="account-settings-card aws-connections-card">
                            <div className="account-settings-card-head">
                                <h2>AWS Account Connections</h2>
                                <p>Add, test, and manage AWS accounts in one clean setup flow</p>
                            </div>

                            <div className="aws-connections-panel">
                                <div className="aws-connections-panel-title">
                                    <span className="aws-connections-chevron">▾</span>
                                    <span>{editingConnectionId ? "Edit AWS Account" : "Add AWS Account"}</span>
                                </div>

                                <div className="aws-connections-form">
                                    <div className="aws-connections-grid">
                                        <label className="account-settings-field">
                                            <span>Connection Name</span>
                                            <input
                                                type="text"
                                                value={connectionForm.connectionName}
                                                onChange={(e) =>
                                                    handleConnectionField("connectionName", e.target.value)
                                                }
                                                placeholder="Production"
                                            />
                                        </label>

                                        <label className="account-settings-field">
                                            <span>IAM Role ARN</span>
                                            <input
                                                type="text"
                                                value={connectionForm.iamRoleArn}
                                                onChange={(e) =>
                                                    handleConnectionField("iamRoleArn", e.target.value)
                                                }
                                                placeholder="arn:aws:iam::123456789012:role/CloudOptimizer"
                                            />
                                        </label>

                                        <label className="account-settings-field">
                                            <span>AWS Account ID</span>
                                            <input
                                                type="text"
                                                value={connectionForm.awsAccountId}
                                                onChange={(e) =>
                                                    handleConnectionField("awsAccountId", e.target.value)
                                                }
                                                placeholder="123456789012"
                                            />
                                        </label>

                                        <label className="account-settings-field">
                                            <span>External ID (Optional)</span>
                                            <input
                                                type="text"
                                                value={connectionForm.externalId}
                                                onChange={(e) =>
                                                    handleConnectionField("externalId", e.target.value)
                                                }
                                                placeholder="Optional"
                                            />
                                        </label>

                                        <label className="account-settings-field full-width">
                                            <span>Primary Region</span>
                                            <select
                                                className="account-settings-select"
                                                value={connectionForm.primaryRegion}
                                                onChange={(e) =>
                                                    handleConnectionField("primaryRegion", e.target.value)
                                                }
                                            >
                                                <option value="us-east-1">us-east-1</option>
                                                <option value="us-east-2">us-east-2</option>
                                                <option value="us-west-1">us-west-1</option>
                                                <option value="us-west-2">us-west-2</option>
                                                <option value="eu-west-1">eu-west-1</option>
                                                <option value="eu-central-1">eu-central-1</option>
                                                <option value="ap-southeast-1">ap-southeast-1</option>
                                                <option value="ap-south-1">ap-south-1</option>
                                            </select>
                                        </label>
                                    </div>

                                    <div className="aws-connections-actions">
                                        <button
                                            type="button"
                                            className="aws-outline-btn"
                                            onClick={handleTestConnection}
                                            disabled={testingConnection}
                                        >
                                            {testingConnection ? "Testing..." : "Test Connection"}
                                        </button>

                                        <div className="aws-connections-actions-right">
                                            {editingConnectionId && (
                                                <button
                                                    type="button"
                                                    className="aws-outline-btn"
                                                    onClick={resetConnectionForm}
                                                >
                                                    Cancel
                                                </button>
                                            )}

                                            <button
                                                type="button"
                                                className="aws-primary-btn"
                                                onClick={handleAddOrUpdateConnection}
                                            >
                                                {editingConnectionId ? "Update Account" : "Add Account"}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className={`aws-feedback-banner ${connections.length > 0 ? "success" : ""}`}>
                                {connectionMessage
                                    ? connectionMessage
                                    : connections.length > 0
                                        ? `${connections.length} AWS account connection${connections.length > 1 ? "s" : ""
                                        } available.`
                                        : "No AWS accounts connected yet. Use the form above to add one."}
                            </div>
                        </section>

                        <section className="account-settings-card">
                            <div className="account-settings-card-head">
                                <h2>Connected Accounts</h2>
                                <p>Review and manage the AWS accounts linked to this workspace</p>
                            </div>

                            {connections.length === 0 ? (
                                <div className="aws-empty-state">
                                    No AWS accounts connected yet. Add one from the form above.
                                </div>
                            ) : (
                                <div className="aws-connections-table-wrap">
                                    <table className="aws-connections-table">
                                        <thead>
                                            <tr>
                                                <th>Connection Name</th>
                                                <th>AWS Account ID</th>
                                                <th>Primary Region</th>
                                                <th>Status</th>
                                                <th>IAM Role ARN</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>

                                        <tbody>
                                            {connections.map((connection) => (
                                                <tr key={connection.id}>
                                                    <td>{connection.connectionName}</td>
                                                    <td>{connection.awsAccountId}</td>
                                                    <td>{connection.primaryRegion}</td>
                                                    <td>
                                                        <span
                                                            className={`aws-status-badge ${connection.status
                                                                .toLowerCase()
                                                                .replace(/\s+/g, "-")}`}
                                                        >
                                                            {connection.status}
                                                        </span>
                                                    </td>
                                                    <td className="aws-role-cell">{connection.iamRoleArn}</td>
                                                    <td>
                                                        <div className="aws-table-actions">
                                                            <button
                                                                type="button"
                                                                className="aws-table-btn"
                                                                onClick={() => handleEditConnection(connection)}
                                                            >
                                                                Edit
                                                            </button>
                                                            <button
                                                                type="button"
                                                                className="aws-table-btn danger"
                                                                onClick={() => handleDeleteConnection(connection.id)}
                                                            >
                                                                Delete
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
                    </>
                )}
            </div>
        </div>
    );
}