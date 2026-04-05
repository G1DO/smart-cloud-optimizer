export type AwsConnection = {
    id: string;
    connectionName: string;
    awsAccountId: string;
    iamRoleArn: string;
    externalId: string;
    primaryRegion: string;
    status: "Connected" | "Not tested" | "Failed";
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

export function getSessionUser(userId?: string | null): SessionUser {
    if (typeof window === "undefined") {
        return getDefaultDemoUser(userId);
    }

    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);

        if (!raw) {
            const fallback = getDefaultDemoUser(userId);
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(fallback));
            return fallback;
        }

        const parsed = JSON.parse(raw) as SessionUser;

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