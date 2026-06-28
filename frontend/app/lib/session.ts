export type AwsConnection = {
    id: string;
    connectionName: string;
    awsAccountId: string;
    iamRoleArn: string;
    externalId: string;
    primaryRegion: string;
    status: "Connected" | "Not tested" | "Failed";
    syncStatus?: "never" | "success" | "failed" | "in_progress";
    lastSyncAt?: string | null;
    errorMessage?: string;
    accessVerified?: boolean;
};

export type SessionUser = {
    userId: string;
    profileName: string;
    email: string;
    awsAccountId: string;
    role: string;
    image: string;
    awsConnections: AwsConnection[];
};

const STORAGE_KEY = "opticloud_current_user";

export function normalizeUserId(input?: string | null): string {
    if (!input) return "synthetic-001";
    return input.trim().toLowerCase();
}

export function getDefaultDemoUser(userId?: string | null): SessionUser {
    const normalized = normalizeUserId(userId);
    const cleanName = normalized.replace(/^aws-/, "");

    return {
        userId: normalized,
        profileName: cleanName,
        email: `${cleanName}@demo.opticloud.ai`,
        awsAccountId: cleanName.toUpperCase(),
        role: "Demo Workspace",
        image: "",
        awsConnections: [],
    };
}

function isSyntheticUserId(input?: string | null): boolean {
    const normalized = normalizeUserId(input);
    return normalized === "aws-synthetic-001" || normalized === "synthetic-001";
}

function getStoredAuthUser(): SessionUser | null {
    if (typeof window === "undefined") return null;

    const storedDemoMode = window.localStorage.getItem("demo_mode") === "true";
    const selectedUser =
        window.localStorage.getItem("selected_user") ||
        window.localStorage.getItem("selectedUser") ||
        "";
    const authUserId =
        window.localStorage.getItem("auth_user_id") ||
        window.localStorage.getItem("user_id") ||
        window.localStorage.getItem("userId") ||
        "";

    const hasRealAuthUser = Boolean(authUserId) && !isSyntheticUserId(authUserId);

    if (
        (storedDemoMode && !hasRealAuthUser) ||
        isSyntheticUserId(authUserId) ||
        (!hasRealAuthUser && isSyntheticUserId(selectedUser))
    ) {
        return getDefaultDemoUser(selectedUser || authUserId || "aws-SYNTHETIC-001");
    }

    if (!authUserId) {
        return null;
    }

    const email = window.localStorage.getItem("auth_email") || "";
    const profileName =
        window.localStorage.getItem("auth_display_name") ||
        (email ? email.split("@")[0] : "Workspace User");

    return {
        userId: authUserId,
        profileName,
        email,
        awsAccountId: "",
        role: "Workspace",
        image: "",
        awsConnections: [],
    };
}

export function getSessionUser(userId?: string | null): SessionUser {
    if (typeof window === "undefined") {
        return getDefaultDemoUser(userId);
    }

    try {
        const authUser = getStoredAuthUser();
        const raw = window.localStorage.getItem(STORAGE_KEY);

        if (!raw) {
            const fallback = authUser ?? getDefaultDemoUser(userId);
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(fallback));
            return fallback;
        }

        const parsed = JSON.parse(raw) as SessionUser;

        if (authUser && normalizeUserId(parsed.userId) !== normalizeUserId(authUser.userId)) {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(authUser));
            return authUser;
        }

        if (authUser) {
            const mergedUser: SessionUser = {
                ...parsed,
                profileName: authUser.profileName || parsed.profileName,
                email: authUser.email || parsed.email,
                role: authUser.role || parsed.role,
                awsAccountId: authUser.awsAccountId || parsed.awsAccountId,
                image: parsed.image || "",
                awsConnections: parsed.awsConnections || [],
            };

            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(mergedUser));
            return mergedUser;
        }

        if (userId) {
            const normalized = normalizeUserId(userId);
            if (normalizeUserId(parsed.userId) !== normalized) {
                const nextUser = getDefaultDemoUser(normalized);
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextUser));
                return nextUser;
            }
        }

        return {
            ...parsed,
            awsConnections: parsed.awsConnections || [],
            image: parsed.image || "",
        };
    } catch {
        const fallback = getDefaultDemoUser(userId);
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(fallback));
        return fallback;
    }
}

export function setSessionUser(user: SessionUser) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
}

export function updateSessionUser(patch: Partial<SessionUser>) {
    if (typeof window === "undefined") return null;

    const current = getSessionUser();
    const updated: SessionUser = {
        ...current,
        ...patch,
        awsConnections: patch.awsConnections ?? current.awsConnections ?? [],
    };

    setSessionUser(updated);
    window.dispatchEvent(new Event("optic-user-updated"));
    return updated;
}

export function clearSessionUser() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(STORAGE_KEY);
}

export function upsertAwsConnection(connection: AwsConnection) {
    const current = getSessionUser();
    const existing = current.awsConnections || [];
    const index = existing.findIndex((item) => item.id === connection.id);

    let nextConnections: AwsConnection[];

    if (index >= 0) {
        nextConnections = [...existing];
        nextConnections[index] = connection;
    } else {
        nextConnections = [...existing, connection];
    }

    updateSessionUser({
        awsConnections: nextConnections,
    });
}

export function deleteAwsConnection(id: string) {
    const current = getSessionUser();
    const nextConnections = (current.awsConnections || []).filter((item) => item.id !== id);

    updateSessionUser({
        awsConnections: nextConnections,
    });
}

export function toAwsConnection(row: any): AwsConnection {
    const syncStatus = row.sync_status as AwsConnection["syncStatus"];

    return {
        id: String(row.id),
        connectionName: row.connection_name ?? "",
        awsAccountId: row.aws_account_id,
        iamRoleArn: row.iam_role_arn,
        externalId: "",
        primaryRegion: row.aws_region,
        syncStatus,
        lastSyncAt: row.last_sync_at ?? null,
        errorMessage: row.error_message ?? "",
        accessVerified: Boolean(row.access_verified),
        status:
            syncStatus === "success"
                ? "Connected"
                : syncStatus === "failed"
                ? "Failed"
                : "Not tested",
    };
}

export function activateConnectedWorkspace(awsAccountId: string, connections: AwsConnection[]) {
    if (typeof window === "undefined") return;

    const realUserId = `aws-${awsAccountId}`;

    window.localStorage.setItem("auth_user_id", realUserId);
    window.localStorage.setItem("demo_mode", "false");

    window.localStorage.removeItem("selected_user");
    window.localStorage.removeItem("selectedUser");
    window.sessionStorage.removeItem("selected_user");
    window.sessionStorage.removeItem("selectedUser");

    updateSessionUser({
        userId: realUserId,
        awsAccountId,
        awsConnections: connections,
    });
}
