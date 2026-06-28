"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import "../home/dashboard.css";
import "./recommendations.css";

type Priority = "high" | "medium" | "low";

type RecommendationItem = {
  id: string;
  service: string;
  recommendation_type: string;
  resource_id: string;
  monthly_savings: number;
  priority: Priority;
  confidence: string;
  current_config: string;
  recommended_config: string;
  current_monthly_cost: number;
  estimated_monthly_cost: number;
  savings_percent: number;
  reasoning: string;
};

type RecommendationsApiResponse = {
  user_id?: string;
  summary?: {
    total_recommendations?: number;
    potential_monthly_savings?: number;
    avg_savings_per_rec?: number;
    high_priority_count?: number;
  };
  recommendations?: RecommendationItem[];
};

type WorkspaceDataState = {
  userId: string;
  isDemoMode: boolean;
  hasConnectedAccount: boolean;
};

const DEFAULT_USER_ID = "aws-SYNTHETIC-001";
const EMPTY_WORKSPACE_STATE: WorkspaceDataState = {
  userId: "",
  isDemoMode: false,
  hasConnectedAccount: false,
};

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function titleize(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function exportCsv(filename: string, rows: Record<string, string | number>[]) {
  if (!rows.length) return;

  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map((row) =>
      headers
        .map((header) => `"${String(row[header]).replace(/"/g, '""')}"`)
        .join(",")
    ),
  ].join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function getServiceEmoji(service: string) {
  const map: Record<string, string> = {
    ec2: "🖥️",
    rds: "🗄️",
    lambda: "⚡",
    s3: "📦",
    ebs: "💾",
    dynamodb: "📊",
    elasticache: "⚡",
    nat_gateway: "🌐",
    vpc: "🌐",
    elb: "⚖️",
  };

  return map[service.toLowerCase()] ?? "☁️";
}

function getPriorityLabel(priority: Priority) {
  if (priority === "high") return "High";
  if (priority === "medium") return "Medium";
  return "Low";
}

function getStoredActiveUserId() {
  if (typeof window === "undefined") return "aws-SYNTHETIC-001";

  const candidates = [
    sessionStorage.getItem("selected_user"),
    sessionStorage.getItem("selectedUser"),
    sessionStorage.getItem("user_id"),
    sessionStorage.getItem("userId"),
    localStorage.getItem("selected_user"),
    localStorage.getItem("selectedUser"),
    localStorage.getItem("user_id"),
    localStorage.getItem("userId"),
  ].filter(Boolean) as string[];

  return candidates[0] || "aws-SYNTHETIC-001";
}

function isSyntheticUserId(value?: string | null) {
  const normalized = (value || "").trim().toLowerCase();
  return normalized === "aws-synthetic-001" || normalized === "synthetic-001";
}

function getWorkspaceDataState(): WorkspaceDataState {
  if (typeof window === "undefined") {
    return EMPTY_WORKSPACE_STATE;
  }

  const storedDemoMode = localStorage.getItem("demo_mode") === "true";
  const selectedUser =
    sessionStorage.getItem("selected_user") ||
    sessionStorage.getItem("selectedUser") ||
    localStorage.getItem("selected_user") ||
    localStorage.getItem("selectedUser") ||
    "";
  const authUserId =
    localStorage.getItem("auth_user_id") ||
    localStorage.getItem("user_id") ||
    localStorage.getItem("userId") ||
    "";

  let sessionUserId = "";
  let connectionCount = 0;

  try {
    const rawUser = localStorage.getItem("opticloud_current_user");
    const parsed = rawUser ? JSON.parse(rawUser) : null;
    sessionUserId = typeof parsed?.userId === "string" ? parsed.userId : "";
    connectionCount = Array.isArray(parsed?.awsConnections)
      ? parsed.awsConnections.length
      : 0;
  } catch {
    sessionUserId = "";
    connectionCount = 0;
  }

  const hasRealAuthUser = Boolean(authUserId) && !isSyntheticUserId(authUserId);
  const isDemoMode =
    (storedDemoMode && !hasRealAuthUser) ||
    isSyntheticUserId(authUserId) ||
    (!hasRealAuthUser && isSyntheticUserId(selectedUser));
  const userId = isDemoMode
    ? selectedUser || authUserId || DEFAULT_USER_ID
    : authUserId || sessionUserId;

  return {
    userId,
    isDemoMode,
    hasConnectedAccount: !isDemoMode && connectionCount > 0,
  };
}

function buildImplementationDetails(rec: RecommendationItem) {
  const implType = (rec.recommendation_type || "").toLowerCase();
  const resourceId = rec.resource_id || "this resource";

  if (implType.includes("right_size") || implType.includes("rightsize")) {
    return {
      intro: "How to implement this recommendation",
      steps: [
        `Review the current utilization and performance metrics for ${resourceId}.`,
        "Verify that the recommended smaller size can still support the workload safely.",
        "Schedule the change during a low-traffic period or maintenance window.",
        "Create a backup or snapshot before applying the resize.",
        "Update the instance or database size to the recommended configuration.",
        "Monitor CPU, memory, latency, and application health after the change.",
      ],
      note:
        "Validate workload performance after resizing and keep a rollback plan ready before applying the change in production.",
    };
  }

  if (
    implType.includes("pricing_plan_switch") ||
    implType.includes("reserved") ||
    implType.includes("spot")
  ) {
    return {
      intro: "How to implement this recommendation",
      steps: [
        `Review the current pricing model used by ${resourceId}.`,
        "Confirm that the workload is stable and predictable enough for a commitment-based plan.",
        "Compare On-Demand cost against Reserved or Spot pricing.",
        "Purchase the Reserved plan or move eligible workloads to Spot capacity.",
        "Add interruption handling or autoscaling safeguards if Spot is used.",
        "Track the savings afterward using billing reports or Cost Explorer.",
      ],
      note:
        "Use commitment-based pricing only for predictable workloads after validating long-term usage stability.",
    };
  }

  if (
    implType.includes("delete") ||
    implType.includes("remove") ||
    implType.includes("delete_unused") ||
    implType.includes("delete_idle")
  ) {
    return {
      intro: "How to implement this recommendation",
      steps: [
        `Verify that ${resourceId} is unused by checking recent activity and monitoring metrics.`,
        "Inspect dependencies such as attached applications, snapshots, routes, and scripts.",
        "Create a final backup or snapshot if recovery may be needed later.",
        "Delete the idle or unused resource from the AWS Console, CLI, or IaC workflow.",
        "Confirm that billing charges for that resource stop appearing afterward.",
      ],
      note:
        "Do not delete the resource before confirming there are no production dependencies or recovery needs.",
    };
  }

  if (
    implType.includes("memory_resize") ||
    implType.includes("memory") ||
    implType.includes("lambda")
  ) {
    return {
      intro: "How to implement this recommendation",
      steps: [
        `Review memory utilization and execution trends for ${resourceId}.`,
        "Check that the recommended memory value still supports peak demand safely.",
        "Update the Lambda memory configuration to the recommended amount.",
        "Run functional and performance tests after the change.",
        "Compare execution duration, error rate, and cost before and after deployment.",
      ],
      note:
        "Lower memory can sometimes increase execution time, so validate both cost and performance after the update.",
    };
  }

  if (
    implType.includes("storage_class_switch") ||
    implType.includes("storage_class") ||
    implType.includes("s3")
  ) {
    return {
      intro: "How to implement this recommendation",
      steps: [
        `Review access frequency and lifecycle behavior for ${resourceId}.`,
        "Confirm that the objects qualify for a lower-cost storage class.",
        "Apply an S3 lifecycle policy or move the objects directly to the new class.",
        "Validate retrieval behavior and expected access performance after the move.",
        "Monitor billing to confirm the expected storage savings.",
      ],
      note:
        "Before changing storage class, confirm retrieval frequency and any retrieval or monitoring charges.",
    };
  }

  if (
    implType.includes("capacity_mode_switch") ||
    implType.includes("capacity_mode") ||
    implType.includes("dynamodb")
  ) {
    return {
      intro: "How to implement this recommendation",
      steps: [
        `Review the actual read/write traffic pattern for ${resourceId}.`,
        "Compare current provisioned capacity with real workload demand.",
        "Switch the table to the recommended capacity mode.",
        "Monitor throttling, latency, and request cost after the change.",
        "Adjust alarms to catch any unexpected traffic spikes quickly.",
      ],
      note:
        "Capacity mode changes affect cost behavior under traffic variation, so monitoring should stay enabled afterward.",
    };
  }

  if (
    implType.includes("replace_with_endpoint") ||
    implType.includes("endpoint") ||
    implType.includes("nat")
  ) {
    return {
      intro: "How to implement this recommendation",
      steps: [
        `Review the traffic currently passing through ${resourceId}.`,
        "Identify AWS service traffic that can be redirected through VPC endpoints.",
        "Create the required gateway or interface endpoints.",
        "Update route tables, DNS, and security group rules if needed.",
        "Test application connectivity after the routing change.",
        "Check the next billing cycle to confirm NAT Gateway cost reduction.",
      ],
      note:
        "Route and DNS changes can affect connectivity, so test carefully after adding VPC endpoints.",
    };
  }

  if (
    implType.includes("volume_type_upgrade") ||
    implType.includes("gp2") ||
    implType.includes("gp3")
  ) {
    return {
      intro: "How to implement this recommendation",
      steps: [
        `Review throughput and IOPS requirements for ${resourceId}.`,
        "Confirm that the recommended volume type still satisfies workload performance needs.",
        "Create a snapshot before modifying the volume.",
        "Change the EBS volume type to the recommended option.",
        "Verify application and disk performance after the update.",
        "Track billing changes to confirm the expected savings.",
      ],
      note:
        "Even if the new EBS volume type is cheaper, validate performance requirements before switching.",
    };
  }

  return {
    intro: "How to implement this recommendation",
    steps: [
      "Review the recommendation details carefully.",
      "Assess the impact on cost, performance, and availability.",
      "Test the change in a safe environment if possible.",
      "Apply the update using AWS Console, CLI, or infrastructure code.",
      "Monitor the workload after deployment to verify the expected result.",
    ],
    note:
      "Always keep a rollback option ready before applying infrastructure changes in production.",
  };
}

function CustomRecommendationsDropdown<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      if (!dropdownRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const selectedOption = options.find((option) => option.value === value) ?? options[0];

  return (
    <div className={`recommendations-dropdown ${open ? "open" : ""}`} ref={dropdownRef}>
      <button
        type="button"
        className="recommendations-dropdown-trigger"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="recommendations-dropdown-value">{selectedOption.label}</span>
        <svg
          className="recommendations-dropdown-arrow"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M6 9L12 15L18 9"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div className="recommendations-dropdown-menu" role="listbox">
          {options.map((option) => {
            const active = option.value === value;

            return (
              <button
                key={String(option.value)}
                type="button"
                className={`recommendations-dropdown-option ${active ? "active" : ""}`}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                <span className="recommendations-dropdown-option-title">{option.label}</span>
                <svg
                  className="recommendations-dropdown-check"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M5 13L9 17L19 7"
                    stroke="currentColor"
                    strokeWidth="2.4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function RecommendationsPage() {
  const [serviceFilter, setServiceFilter] = useState("All");
  const [typeFilter, setTypeFilter] = useState("All");
  const [priorityFilter, setPriorityFilter] = useState("All");
  const [minSavings, setMinSavings] = useState(0);
  const [sortBy, setSortBy] = useState("High to Low");
  const [isDark, setIsDark] = useState(false);
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [expandedImplementationIds, setExpandedImplementationIds] = useState<string[]>([]);
  const [allRecommendations, setAllRecommendations] = useState<RecommendationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeUserId, setActiveUserId] = useState("aws-SYNTHETIC-001");
  const [workspaceState, setWorkspaceState] =
    useState<WorkspaceDataState>(EMPTY_WORKSPACE_STATE);
  const [apiSummary, setApiSummary] = useState<RecommendationsApiResponse["summary"]>();
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const updateDarkMode = () => {
      const shell =
        wrapperRef.current?.closest(".dashboard-shell") ??
        document.querySelector(".dashboard-shell");

      setIsDark(shell?.classList.contains("dashboard-dark") ?? false);
    };

    updateDarkMode();

    const observer = new MutationObserver(updateDarkMode);
    const target =
      wrapperRef.current?.closest(".dashboard-shell") ??
      document.querySelector(".dashboard-shell");

    if (target) {
      observer.observe(target, {
        attributes: true,
        attributeFilter: ["class"],
      });
    }

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const syncActiveUser = () => {
      const nextWorkspaceState = getWorkspaceDataState();
      setWorkspaceState(nextWorkspaceState);
      setActiveUserId(nextWorkspaceState.userId || getStoredActiveUserId());
    };

    syncActiveUser();

    window.addEventListener("storage", syncActiveUser);
    window.addEventListener("optic-user-updated", syncActiveUser as EventListener);

    return () => {
      window.removeEventListener("storage", syncActiveUser);
      window.removeEventListener("optic-user-updated", syncActiveUser as EventListener);
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    async function fetchRecommendations() {
      if (!workspaceState.isDemoMode && !workspaceState.hasConnectedAccount) {
        setLoading(false);
        setError("");
        setAllRecommendations([]);
        setApiSummary(undefined);
        return;
      }

      if (!activeUserId) {
        setLoading(false);
        setError("");
        setAllRecommendations([]);
        setApiSummary(undefined);
        return;
      }

      try {
        setLoading(true);
        setError("");

        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
        const generateIfEmpty = workspaceState.isDemoMode ? "true" : "false";

        const response = await fetch(
          `${apiBase}/api/recommendations?user_id=${encodeURIComponent(
            activeUserId
          )}&generate_if_empty=${generateIfEmpty}`,
          { cache: "no-store" }
        );

        if (!response.ok) {
          let detail = `Failed to fetch recommendations: ${response.status}`;
          try {
            const err = await response.json();
            if (err?.detail) detail = String(err.detail);
          } catch { }
          throw new Error(detail);
        }

        const data: RecommendationsApiResponse = await response.json();

        if (!ignore) {
          setAllRecommendations(Array.isArray(data.recommendations) ? data.recommendations : []);
          setApiSummary(data.summary);
        }
      } catch (fetchError) {
        console.error("Failed to load recommendations from backend:", fetchError);
        if (!ignore) {
          setAllRecommendations([]);
          setApiSummary(undefined);
          setError(fetchError instanceof Error ? fetchError.message : "Something went wrong.");
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    fetchRecommendations();

    return () => {
      ignore = true;
    };
  }, [
    activeUserId,
    workspaceState.isDemoMode,
    workspaceState.hasConnectedAccount,
  ]);

  const services = useMemo(
    () => ["All", ...Array.from(new Set(allRecommendations.map((r) => r.service))).sort()],
    [allRecommendations]
  );

  const recommendationTypes = useMemo(
    () => [
      "All",
      ...Array.from(new Set(allRecommendations.map((r) => r.recommendation_type))).sort(),
    ],
    [allRecommendations]
  );

  const serviceOptions = useMemo(
    () =>
      services.map((service) => ({
        value: service,
        label: service === "All" ? "All Services" : titleize(service),
      })),
    [services]
  );

  const typeOptions = useMemo(
    () =>
      recommendationTypes.map((type) => ({
        value: type,
        label: type === "All" ? "All Recommendation Types" : titleize(type),
      })),
    [recommendationTypes]
  );

  const priorityOptions = useMemo(
    () => [
      { value: "All", label: "All Priorities" },
      { value: "high", label: "High" },
      { value: "medium", label: "Medium" },
      { value: "low", label: "Low" },
    ],
    []
  );

  const sortOptions = useMemo(
    () => [
      { value: "High to Low", label: "High to Low" },
      { value: "Low to High", label: "Low to High" },
      { value: "Priority", label: "Priority" },
      { value: "Service", label: "Service" },
    ],
    []
  );

  const filteredRecommendations = useMemo(() => {
    let result = [...allRecommendations];

    if (serviceFilter !== "All") {
      result = result.filter((r) => r.service === serviceFilter);
    }

    if (typeFilter !== "All") {
      result = result.filter((r) => r.recommendation_type === typeFilter);
    }

    if (priorityFilter !== "All") {
      result = result.filter((r) => r.priority === priorityFilter);
    }

    result = result.filter((r) => r.monthly_savings >= minSavings);

    if (sortBy === "High to Low") {
      result.sort((a, b) => b.monthly_savings - a.monthly_savings);
    } else if (sortBy === "Low to High") {
      result.sort((a, b) => a.monthly_savings - b.monthly_savings);
    } else if (sortBy === "Priority") {
      const order: Record<Priority, number> = { high: 0, medium: 1, low: 2 };
      result.sort((a, b) => order[a.priority] - order[b.priority]);
    } else if (sortBy === "Service") {
      result.sort((a, b) => a.service.localeCompare(b.service));
    }

    return result;
  }, [allRecommendations, serviceFilter, typeFilter, priorityFilter, minSavings, sortBy]);

  const totalRecommendations =
    typeof apiSummary?.total_recommendations === "number"
      ? apiSummary.total_recommendations
      : allRecommendations.length;

  const totalSavings =
    typeof apiSummary?.potential_monthly_savings === "number"
      ? apiSummary.potential_monthly_savings
      : allRecommendations.reduce((sum, rec) => sum + rec.monthly_savings, 0);

  const avgSavings =
    typeof apiSummary?.avg_savings_per_rec === "number"
      ? apiSummary.avg_savings_per_rec
      : allRecommendations.length > 0
        ? allRecommendations.reduce((sum, rec) => sum + rec.monthly_savings, 0) /
        allRecommendations.length
        : 0;

  const mediumPriorityCount = allRecommendations.filter((r) => r.priority === "medium").length;

  const filteredSavings = filteredRecommendations.reduce((sum, rec) => sum + rec.monthly_savings, 0);

  const exportRows = filteredRecommendations.map((rec) => ({
    service: rec.service,
    recommendation_type: rec.recommendation_type,
    resource_id: rec.resource_id,
    monthly_savings: rec.monthly_savings.toFixed(2),
    priority: rec.priority,
    confidence: rec.confidence,
    current_config: rec.current_config,
    recommended_config: rec.recommended_config,
    current_monthly_cost: rec.current_monthly_cost.toFixed(2),
    estimated_monthly_cost: rec.estimated_monthly_cost.toFixed(2),
    savings_percent: rec.savings_percent.toFixed(1),
    reasoning: rec.reasoning,
  }));

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const toggleImplementationExpanded = (id: string) => {
    setExpandedImplementationIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  return (
    <div ref={wrapperRef} className={`${isDark ? "dashboard-dark" : ""}`}>
      <div className="recommendations-page">
        <section className="recommendations-hero">
          <span className="recommendations-hero-badge">
            <span className="recommendations-hero-badge-star">✦</span>
            Optimization Decision Center
          </span>

          <h1>Convert cost signals into cleaner, smarter AWS actions</h1>
          <h2>Review and filter cost-saving recommendations clearly</h2>

          <p>
            Focus on service, recommendation type, priority, and savings impact with a cleaner
            recommendations workflow.
          </p>
        </section>

        <section className="recommendations-kpi-grid">
          <article className="recommendations-kpi-card recommendations-kpi-card--total">
            <div className="recommendations-kpi-top">
              <span>Total Recommendations</span>
              <div className="recommendations-kpi-icon" />
            </div>
            <h3>{loading ? "..." : totalRecommendations}</h3>
            <p>Optimization opportunities currently available</p>
            <div className="recommendations-kpi-line" />
          </article>

          <article className="recommendations-kpi-card recommendations-kpi-card--savings">
            <div className="recommendations-kpi-top">
              <span>Potential Monthly Savings</span>
              <div className="recommendations-kpi-icon" />
            </div>
            <h3>{loading ? "..." : formatCurrency(totalSavings)}</h3>
            <p>Total estimated monthly reduction</p>
            <div className="recommendations-kpi-line" />
          </article>

          <article className="recommendations-kpi-card recommendations-kpi-card--avg">
            <div className="recommendations-kpi-top">
              <span>Avg Savings per Rec</span>
              <div className="recommendations-kpi-icon" />
            </div>
            <h3>{loading ? "..." : formatCurrency(avgSavings)}</h3>
            <p>Average savings value per recommendation</p>
            <div className="recommendations-kpi-line" />
          </article>

          <article className="recommendations-kpi-card recommendations-kpi-card--medium">
            <div className="recommendations-kpi-top">
              <span>Medium Priority</span>
              <div className="recommendations-kpi-icon" />
            </div>
            <h3>{loading ? "..." : mediumPriorityCount}</h3>
            <p>
              {loading
                ? "..."
                : mediumPriorityCount > 0
                  ? "Medium-priority optimization items"
                  : "No medium-priority items currently"}
            </p>
            <div className="recommendations-kpi-line" />
          </article>
        </section>

        <section className="dashboard-card recommendations-filters-card">
          <div className="recommendations-filters-top">
            <div className="card-header compact">
              <div>
                <p className="card-eyebrow">Filter & Sort</p>
                <h3>Focus the recommendation queue</h3>
              </div>
            </div>

            <button
              type="button"
              className="recommendations-reset-btn"
              onClick={() => {
                setServiceFilter("All");
                setTypeFilter("All");
                setPriorityFilter("All");
                setMinSavings(0);
                setSortBy("High to Low");
              }}
            >
              Reset
            </button>
          </div>

          <div className="recommendations-filter-grid">
            <label className="recommendations-field">
              <span>Service</span>
              <CustomRecommendationsDropdown
                value={serviceFilter}
                options={serviceOptions}
                onChange={setServiceFilter}
              />
            </label>

            <label className="recommendations-field">
              <span>Recommendation Type</span>
              <CustomRecommendationsDropdown
                value={typeFilter}
                options={typeOptions}
                onChange={setTypeFilter}
              />
            </label>

            <label className="recommendations-field">
              <span>Priority</span>
              <CustomRecommendationsDropdown
                value={priorityFilter}
                options={priorityOptions}
                onChange={setPriorityFilter}
              />
            </label>

            <label className="recommendations-field">
              <span>Min Savings</span>
              <input
                type="number"
                min={0}
                step={10}
                value={minSavings}
                onChange={(e) => setMinSavings(Number(e.target.value) || 0)}
              />
            </label>

            <label className="recommendations-field">
              <span>Sort By</span>
              <CustomRecommendationsDropdown
                value={sortBy}
                options={sortOptions}
                onChange={setSortBy}
              />
            </label>
          </div>
        </section>

        <section className="recommendations-results-wrap">
          <div className="recommendations-results-head">
            <div className="recommendations-results-copy">
              <h3>
                {loading
                  ? "Loading recommendations..."
                  : `Showing ${filteredRecommendations.length} recommendation${filteredRecommendations.length === 1 ? "" : "s"
                  }`}
              </h3>
              <p>
                {loading
                  ? "Pulling optimization actions from the backend."
                  : `${formatCurrency(filteredSavings)} / month potential savings for the current filter set.`}
              </p>
            </div>

            <div className="recommendations-results-actions">
              <button
                type="button"
                className="recommendations-export-btn"
                onClick={() => exportCsv(`recommendations_${activeUserId}.csv`, exportRows)}
                disabled={loading || filteredRecommendations.length === 0}
              >
                Export CSV
              </button>

              <button
                type="button"
                className="recommendations-mark-btn"
                onClick={() => {
                  const allIds = filteredRecommendations.map((rec) => rec.id);
                  setExpandedIds((prev) => (prev.length === allIds.length ? [] : allIds));
                }}
                disabled={loading || filteredRecommendations.length === 0}
              >
                {expandedIds.length === filteredRecommendations.length &&
                  filteredRecommendations.length
                  ? "Collapse All"
                  : "Expand All"}
              </button>
            </div>
          </div>

          {error ? (
            <div className="recommendations-empty">
              <div>
                <strong>Failed to load recommendations</strong>
                <p>{error}</p>
              </div>
            </div>
          ) : loading ? (
            <div className="recommendations-empty">
              <div>
                <strong>Loading recommendations...</strong>
                <p>We are fetching the latest optimizer results from the backend.</p>
              </div>
            </div>
          ) : filteredRecommendations.length === 0 ? (
            <div className="recommendations-empty">
              <div>
                <strong>No recommendations match your filters</strong>
                <p>Try adjusting the filters above to show more results.</p>
              </div>
            </div>
          ) : (
            <div className="recommendations-list">
              {filteredRecommendations.map((rec) => {
                const isExpanded = expandedIds.includes(rec.id);
                const isImplementationExpanded = expandedImplementationIds.includes(rec.id);
                const serviceEmoji = getServiceEmoji(rec.service);
                const implementation = buildImplementationDetails(rec);

                return (
                  <article key={rec.id} className={`recommendation-card priority-${rec.priority}`}>
                    <button
                      type="button"
                      className="recommendation-compact-header"
                      onClick={() => toggleExpanded(rec.id)}
                    >
                      <div className="recommendation-compact-left">
                        <div className="recommendation-topline">
                          <span className="recommendation-chip service">
                            {serviceEmoji} {titleize(rec.service)}
                          </span>
                          <span className={`recommendation-chip priority-${rec.priority}`}>
                            {getPriorityLabel(rec.priority)} Priority
                          </span>
                          <span className="recommendation-chip confidence">
                            {titleize(rec.confidence)} Confidence
                          </span>
                        </div>

                        <h3 className="recommendation-title">
                          {titleize(rec.recommendation_type)}
                        </h3>
                        <p className="recommendation-resource">Resource: {rec.resource_id}</p>
                        <span className="recommendation-expand-note">
                          Click to {isExpanded ? "collapse" : "expand"}
                        </span>
                      </div>

                      <div className="recommendation-compact-right">
                        <div className="recommendation-compact-label">
                          Potential Monthly Savings
                        </div>
                        <div className="recommendation-compact-savings">
                          {formatCurrency(rec.monthly_savings)}
                        </div>
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="recommendation-expanded-body">
                        <div className="recommendation-card-main no-rail">
                          <div className="recommendation-left">
                            <div className="recommendation-change-grid">
                              <div className="recommendation-config-box">
                                <span>Current</span>
                                <strong>{rec.current_config}</strong>
                              </div>

                              <div className="recommendation-change-arrow">→</div>

                              <div className="recommendation-config-box">
                                <span>Recommended</span>
                                <strong>{rec.recommended_config}</strong>
                              </div>
                            </div>

                            <div className="recommendation-impact-row">
                              <div className="recommendation-impact-box">
                                <span>Current Monthly Cost</span>
                                <strong>{formatCurrency(rec.current_monthly_cost)}</strong>
                              </div>

                              <div className="recommendation-impact-box">
                                <span>Estimated Monthly Cost</span>
                                <strong>{formatCurrency(rec.estimated_monthly_cost)}</strong>
                              </div>

                              <div className="recommendation-impact-box">
                                <span>Savings Percent</span>
                                <strong>{rec.savings_percent.toFixed(1)}%</strong>
                              </div>
                            </div>

                            <div className="recommendation-why-box">
                              <div className="recommendation-why-title">Why This Matters</div>
                              <div className="recommendation-why-text">
                                {rec.reasoning || "No additional reasoning was provided."}
                              </div>
                            </div>

                            <div className="recommendation-details-inline">
                              <button
                                type="button"
                                className={`recommendation-details-toggle ${isImplementationExpanded ? "open" : ""
                                  }`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleImplementationExpanded(rec.id);
                                }}
                              >
                                <span>{implementation.intro}</span>
                                <span className="recommendation-details-toggle-icon">
                                  {isImplementationExpanded ? "−" : "+"}
                                </span>
                              </button>

                              {isImplementationExpanded && (
                                <div className="recommendation-details-body">
                                  <ol className="recommendation-steps">
                                    {implementation.steps.map((step, index) => (
                                      <li key={`${rec.id}-step-${index}`}>{step}</li>
                                    ))}
                                  </ol>

                                  <div className="recommendation-note">
                                    ⚠️ {implementation.note}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
