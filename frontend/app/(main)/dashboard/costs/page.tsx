
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Plotly from "plotly.js-dist-min";
import type { Layout, Config, Data } from "plotly.js";
import "../home/dashboard.css";
import "./costs.css";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type DailyCostPoint = {
  date: string;
  total_cost: number;
};

type ServiceCostPoint = {
  service: string;
  total_cost: number;
};

type ServiceTimelinePoint = {
  date: string;
  service: string;
  daily_cost: number;
};

type PresetType =
  | "Last 7 Days"
  | "Last 30 Days"
  | "Last 90 Days"
  | "Last 6 Months"
  | "Last Year"
  | "All Time"
  | "Custom";

type CostsSummaryApi = {
  total_cost: number;
  avg_daily: number;
  min_daily: number;
  max_daily: number;
  change_pct: number | null;
};

type DateRangeInfo = {
  preset: PresetType;
  start_date: string;
  end_date: string;
  days_count: number;
  label: string;
};

type AvailableRangeInfo = {
  start_date: string | null;
  end_date: string | null;
};

type CostsApiResponse = {
  user_id: string;
  date_range: DateRangeInfo;
  available_range: AvailableRangeInfo;
  summary: CostsSummaryApi;
  daily_costs: DailyCostPoint[];
  service_breakdown: Array<{
    service: string;
    total_cost: number;
    percent: number;
  }>;
  service_timeline: ServiceTimelinePoint[];
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

const DEFAULT_USER_ID = "aws-SYNTHETIC-001";

type WorkspaceDataState = {
  userId: string;
  isDemoMode: boolean;
  hasConnectedAccount: boolean;
};

const EMPTY_WORKSPACE_STATE: WorkspaceDataState = {
  userId: "",
  isDemoMode: false,
  hasConnectedAccount: false,
};

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
    localStorage.getItem("selected_user") || localStorage.getItem("selectedUser") || "";
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

const PRESET_OPTIONS: {
  value: PresetType;
  subtitle: string;
}[] = [
    { value: "Last 7 Days", subtitle: "Short recent view" },
    { value: "Last 30 Days", subtitle: "Best for monthly review" },
    { value: "Last 90 Days", subtitle: "Quarterly trend check" },
    { value: "Last 6 Months", subtitle: "Mid-term visibility" },
    { value: "Last Year", subtitle: "Long-term analysis" },
    { value: "All Time", subtitle: "Everything available" },
    { value: "Custom", subtitle: "Pick your own date range" },
  ];

/**
 * رجّعنا ألوان نسخة الـ mock
 * ودعمنا كمان الأسماء المختصرة اللي بتيجي من الـ backend
 */
const SERVICE_COLORS: Record<string, string> = {
  "Amazon EC2": "#1f79ffc6",
  EC2: "#1f79ffc6",

  "Amazon RDS": "#6431cbc6",
  RDS: "#6431cbc6",

  "AWS Lambda": "#f4e921c6",
  Lambda: "#f4e921c6",

  "Amazon S3": "#24c274c6",
  S3: "#24c274c6",

  "NAT Gateway": "#f5800bc6",

  "Amazon EBS": "#e81f1fc6",
  EBS: "#e81f1fc6",

  Other: "#103c78c6",
};

const SERVICE_DISPLAY_NAME: Record<string, string> = {
  "Amazon EC2": "Amazon EC2",
  EC2: "EC2",

  "Amazon RDS": "Amazon RDS",
  RDS: "RDS",

  "AWS Lambda": "AWS Lambda",
  Lambda: "Lambda",

  "Amazon S3": "Amazon S3",
  S3: "S3",

  "NAT Gateway": "NAT Gateway",

  "Amazon EBS": "Amazon EBS",
  EBS: "EBS",

  Other: "Other",
};

const SERVICE_SHORT_NAME: Record<string, string> = {
  "Amazon EC2": "EC2",
  EC2: "EC2",

  "Amazon RDS": "RDS",
  RDS: "RDS",

  "AWS Lambda": "Lambda",
  Lambda: "Lambda",

  "Amazon S3": "S3",
  S3: "S3",

  "NAT Gateway": "NAT Gateway",

  "Amazon EBS": "EBS",
  EBS: "EBS",

  Other: "Other",
};

const SERVICE_SORT_ORDER: Record<string, number> = {
  "Amazon EC2": 1,
  EC2: 1,

  "Amazon RDS": 2,
  RDS: 2,

  "AWS Lambda": 3,
  Lambda: 3,

  "Amazon S3": 4,
  S3: 4,

  "NAT Gateway": 5,

  "Amazon EBS": 6,
  EBS: 6,

  Other: 7,
};

function getServiceColor(service: string) {
  return SERVICE_COLORS[service] || "#94a3b8";
}

function getServiceDisplayName(service: string) {
  return SERVICE_DISPLAY_NAME[service] || service;
}

function getServiceShortName(service: string) {
  return SERVICE_SHORT_NAME[service] || service.replace("Amazon ", "").replace("AWS ", "");
}

function getServiceOrder(service: string) {
  return SERVICE_SORT_ORDER[service] ?? 999;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatCurrencyPrecise(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number | null | undefined) {
  const safe = value ?? 0;
  return `${safe >= 0 ? "+" : ""}${safe.toFixed(1)}%`;
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

function zoomDateRange(
  currentRange: [string, string] | undefined,
  fallbackDates: string[],
  factor: number
): [string, string] {
  const safeDates =
    fallbackDates.length > 0
      ? fallbackDates
      : [new Date().toISOString(), new Date().toISOString()];

  const start = new Date(currentRange?.[0] ?? safeDates[0]).getTime();
  const end = new Date(
    currentRange?.[1] ?? safeDates[safeDates.length - 1]
  ).getTime();
  const center = (start + end) / 2;
  const half = ((end - start) * factor) / 2;

  return [
    new Date(center - half).toISOString(),
    new Date(center + half).toISOString(),
  ];
}

function zoomNumberRange(
  currentRange: [number, number] | undefined,
  fallbackMin: number,
  fallbackMax: number,
  factor: number
): [number, number] {
  const start = currentRange?.[0] ?? fallbackMin;
  const end = currentRange?.[1] ?? fallbackMax;
  const center = (start + end) / 2;
  const half = ((end - start) * factor) / 2;
  return [center - half, center + half];
}

function ToolbarButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void | Promise<void>;
  children: React.ReactNode;
}) {
  const handleClick = () => {
    void Promise.resolve(onClick()).catch((error) => {
      console.error(`${label} action failed`, error);
    });
  };

  return (
    <button
      type="button"
      className="cost-chart-tool-btn"
      onClick={handleClick}
      title={label}
      aria-label={label}
    >
      {children}
    </button>
  );
}

function ChartToolbar({
  onCsvDownload,
  onPngDownload,
  onZoomIn,
  onZoomOut,
  onReset,
  onFullscreen,
}: {
  onCsvDownload: () => void;
  onPngDownload: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onFullscreen: () => void;
}) {
  return (
    <div className="cost-chart-tools">
      <ToolbarButton label="Download CSV" onClick={onCsvDownload}>
        <img
          src="/icons/imagebar/download.png"
          alt="download"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Download plot as PNG" onClick={onPngDownload}>
        <img
          src="/icons/imagebar/camera.png"
          alt="camera"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Zoom in" onClick={onZoomIn}>
        <img
          src="/icons/imagebar/zoomin.png"
          alt="zoomin"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Zoom out" onClick={onZoomOut}>
        <img
          src="/icons/imagebar/zoomout.png"
          alt="zoomout"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Reset axes" onClick={onReset}>
        <img
          src="/icons/imagebar/reset.png"
          alt="reset"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Full screen" onClick={onFullscreen}>
        <img
          src="/icons/imagebar/full.png"
          alt="full"
          className="bar-icon-img"
        />
      </ToolbarButton>
    </div>
  );
}

function CustomPresetDropdown({
  value,
  onChange,
}: {
  value: PresetType;
  onChange: (value: PresetType) => void;
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
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const selectedOption =
    PRESET_OPTIONS.find((option) => option.value === value) ?? PRESET_OPTIONS[1];

  return (
    <div className={`costs-dropdown ${open ? "open" : ""}`} ref={dropdownRef}>
      <button
        type="button"
        className="costs-dropdown-trigger"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="costs-dropdown-value-wrap">
          <span className="costs-dropdown-value-label">Selected range</span>
          <span className="costs-dropdown-value">{selectedOption.value}</span>
        </span>

        <svg
          className="costs-dropdown-arrow"
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
        <div className="costs-dropdown-menu" role="listbox">
          {PRESET_OPTIONS.map((option) => {
            const active = option.value === value;

            return (
              <button
                key={option.value}
                type="button"
                className={`costs-dropdown-option ${active ? "active" : ""}`}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                <span className="costs-dropdown-option-main">
                  <span className="costs-dropdown-option-title">
                    {option.value}
                  </span>
                  <span className="costs-dropdown-option-subtitle">
                    {option.subtitle}
                  </span>
                </span>

                <svg
                  className="costs-dropdown-check"
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

export default function CostsPage() {
  const [workspaceState, setWorkspaceState] =
    useState<WorkspaceDataState>(EMPTY_WORKSPACE_STATE);
  const [preset, setPreset] = useState<PresetType>("Last 30 Days");
  const [showRecords, setShowRecords] = useState(false);
  const [customStartDate, setCustomStartDate] = useState("");
  const [customEndDate, setCustomEndDate] = useState("");

  const [apiData, setApiData] = useState<CostsApiResponse | null>(null);

  useEffect(() => {
    const syncWorkspaceState = () => {
      setWorkspaceState(getWorkspaceDataState());
    };

    syncWorkspaceState();

    window.addEventListener("storage", syncWorkspaceState);
    window.addEventListener("optic-user-updated", syncWorkspaceState);

    return () => {
      window.removeEventListener("storage", syncWorkspaceState);
      window.removeEventListener("optic-user-updated", syncWorkspaceState);
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    async function loadCosts() {
      if (!workspaceState.isDemoMode && !workspaceState.hasConnectedAccount) {
        setApiData(null);
        return;
      }

      if (!workspaceState.userId) {
        setApiData(null);
        return;
      }

      if (preset === "Custom" && (!customStartDate || !customEndDate)) {
        return;
      }

      try {
        const params = new URLSearchParams();
        params.set("user_id", workspaceState.userId);
        params.set("preset", preset);

        if (preset === "Custom") {
          params.set("start_date", customStartDate);
          params.set("end_date", customEndDate);
        }

        const response = await fetch(`${API_BASE}/api/costs?${params.toString()}`, {
          cache: "no-store",
        });

        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload?.detail || "Failed to load costs data.");
        }

        if (!ignore) {
          setApiData(payload);

          if (!customStartDate && payload?.available_range?.start_date) {
            setCustomStartDate(payload.available_range.start_date);
          }

          if (!customEndDate && payload?.available_range?.end_date) {
            setCustomEndDate(payload.available_range.end_date);
          }
        }
      } catch {
        if (!ignore) {
          setApiData(null);
        }
      }
    }

    loadCosts();

    return () => {
      ignore = true;
    };
  }, [
    workspaceState.userId,
    workspaceState.isDemoMode,
    workspaceState.hasConnectedAccount,
    preset,
    customStartDate,
    customEndDate,
  ]);

  const filteredDailyCosts = apiData?.daily_costs ?? [];

  const serviceCosts: ServiceCostPoint[] = (apiData?.service_breakdown ?? [])
    .map((item) => ({
      service: item.service,
      total_cost: item.total_cost,
    }))
    .sort((a, b) => getServiceOrder(a.service) - getServiceOrder(b.service));

  const serviceTimeline = apiData?.service_timeline ?? [];

  const availableTimelineServices = useMemo(
    () =>
      Array.from(new Set(serviceTimeline.map((item) => item.service))).sort(
        (a, b) => getServiceOrder(a) - getServiceOrder(b)
      ),
    [serviceTimeline]
  );

  const [visibleServices, setVisibleServices] = useState<string[]>([]);
  useEffect(() => {
    setVisibleServices((currentServices) => {
      const sameLength = currentServices.length === availableTimelineServices.length;
      const sameItems =
        sameLength &&
        currentServices.every((service, index) => service === availableTimelineServices[index]);

      return sameItems ? currentServices : availableTimelineServices;
    });
  }, [availableTimelineServices]);

  function toggleVisibleService(service: string) {
    setVisibleServices((prev) =>
      prev.includes(service)
        ? prev.filter((item) => item !== service)
        : [...prev, service]
    );
  }

  function showOnlyService(service: string) {
    setVisibleServices([service]);
  }

  function resetVisibleServices() {
    setVisibleServices(availableTimelineServices);
  }

  const summary = useMemo(() => {
    const apiSummary = apiData?.summary;

    return {
      totalCost: apiSummary?.total_cost ?? 0,
      avgDaily: apiSummary?.avg_daily ?? 0,
      minDaily: apiSummary?.min_daily ?? 0,
      maxDaily: apiSummary?.max_daily ?? 0,
      changePct: apiSummary?.change_pct ?? 0,
    };
  }, [apiData]);

  const serviceTableRows = useMemo(() => {
    const apiBreakdown = [...(apiData?.service_breakdown ?? [])].sort(
      (a, b) => b.total_cost - a.total_cost
    );

    return apiBreakdown.map((item) => ({
      service: item.service,
      total_cost: item.total_cost,
      percent: item.percent,
      color: getServiceColor(item.service),
    }));
  }, [apiData]);

  const startDate = apiData?.date_range?.start_date ?? "";
  const endDate = apiData?.date_range?.end_date ?? "";
  const dateRangeLabel =
    apiData?.date_range?.label ?? `${startDate} to ${endDate}`;
  const presetLabel = apiData?.date_range?.preset ?? preset;

  const distributionTotal = serviceTableRows.reduce(
    (sum, row) => sum + row.total_cost,
    0
  );

  const dailyGraphRef = useRef<any>(null);
  const dailyWrapperRef = useRef<HTMLDivElement | null>(null);

  const barGraphRef = useRef<any>(null);
  const barWrapperRef = useRef<HTMLDivElement | null>(null);

  const pieGraphRef = useRef<any>(null);
  const pieWrapperRef = useRef<HTMLDivElement | null>(null);

  const serviceGraphRef = useRef<any>(null);
  const serviceWrapperRef = useRef<HTMLDivElement | null>(null);

  const dailyXValues = filteredDailyCosts.map((item) => item.date);
  const dailyYValues = filteredDailyCosts.map((item) => item.total_cost);
  const dailyMinY = dailyYValues.length ? Math.min(...dailyYValues) : 0;
  const dailyMaxY = dailyYValues.length ? Math.max(...dailyYValues) : 0;
  const dailyPaddedMinY = Math.max(
    0,
    dailyMinY - Math.max(10, Math.round((dailyMaxY - dailyMinY) * 0.18))
  );
  const dailyPaddedMaxY =
    dailyMaxY + Math.max(10, Math.round((dailyMaxY - dailyMinY) * 0.18));

  const barMaxX = Math.max(...serviceTableRows.map((item) => item.total_cost), 0);
  const barPaddedMaxX = barMaxX + Math.max(120, Math.round(barMaxX * 0.15));

  const pieValues = serviceTableRows.map((item) => item.total_cost);
  const pieLabels = serviceTableRows.map((item) => getServiceDisplayName(item.service));

  const serviceGroupedDates = Array.from(
    new Set(serviceTimeline.map((item) => item.date))
  ).sort();

  const serviceValues = serviceTimeline
    .filter((item) => visibleServices.includes(item.service))
    .map((item) => item.daily_cost);

  const serviceMinY = serviceValues.length ? Math.min(...serviceValues) : 0;
  const serviceMaxY = serviceValues.length ? Math.max(...serviceValues) : 0;
  const servicePaddedMinY = Math.max(
    0,
    serviceMinY - Math.max(5, Math.round((serviceMaxY - serviceMinY) * 0.2))
  );
  const servicePaddedMaxY =
    serviceMaxY + Math.max(5, Math.round((serviceMaxY - serviceMinY) * 0.2));

  const commonPlotConfig: Partial<Config> = {
    responsive: true,
    displayModeBar: false,
    displaylogo: false,
    scrollZoom: true,
  };

  const dailyData: Partial<Data>[] = [
    {
      x: dailyXValues,
      y: dailyYValues,
      type: "scatter",
      mode: "lines",
      line: { color: "#2d6cf6", width: 4 },
      hoverlabel: {
        bgcolor: "#ffffff",
        bordercolor: "rgba(15, 52, 107, 0.14)",
        font: { color: "#4c5d79", size: 12 },
      },
      hovertemplate:
        "<b>%{x|%b %-d, %Y}</b><br>" +
        "Date=%{x|%b %-d, %Y}<br>" +
        "Cost (USD)=%{y:.2f}<extra></extra>",
      showlegend: false,
    },
  ];

  const dailyLayout: Partial<Layout> = {
    autosize: true,
    height: 560,
    margin: { l: 82, r: 28, t: 12, b: 70 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    showlegend: false,
    hovermode: "closest",
    dragmode: "zoom",
    xaxis: {
      title: { text: "Date", font: { size: 16, color: "#001938" } },
      type: "date",
      tickformat: "%b %-d",
      color: "#001938",
      tickfont: { size: 12 },
      showgrid: false,
      zeroline: false,
      showline: false,
      automargin: true,
    },
    yaxis: {
      title: { text: "Cost (USD)", font: { size: 16, color: "#001938" } },
      color: "#001938",
      tickfont: { size: 12 },
      tickprefix: "$",
      showgrid: true,
      gridcolor: "#00193841",
      gridwidth: 1,
      zeroline: false,
      showline: false,
      rangemode: "tozero",
      automargin: true,
    },
  };

  const barData: Partial<Data>[] = [
    {
      x: serviceTableRows.map((item) => item.total_cost),
      y: serviceTableRows.map((item) => getServiceShortName(item.service)),
      type: "bar",
      orientation: "h",
      marker: {
        color: serviceTableRows.map((item) => item.color),
        line: {
          color: "rgba(255,255,255,0.45)",
          width: 1,
        },
      },
      hoverlabel: {
        bgcolor: "#ffffff",
        bordercolor: "rgba(15, 52, 107, 0.14)",
        font: { color: "#001938", size: 12 },
      },
      hovertemplate: "<b>%{y}</b><br>Cost (USD)=%{x:.2f}<extra></extra>",
      showlegend: false,
    },
  ];

  const barLayout: Partial<Layout> = {
    autosize: true,
    height: 460,
    margin: { l: 96, r: 18, t: 10, b: 60 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    bargap: 0.22,
    showlegend: false,
    xaxis: {
      title: { text: "Cost (USD)", font: { size: 14, color: "#001938" } },
      color: "#001938",
      gridcolor: "#00193829",
      tickfont: { size: 12 },
      showgrid: false,
      zeroline: false,
      rangemode: "tozero",
    },
    yaxis: {
      color: "#001938",
      tickfont: { size: 14 },
      autorange: "reversed",
      showgrid: false,
      zeroline: false,
    },
  };

  const pieData: Partial<Data>[] = [
    {
      type: "pie",
      values: pieValues,
      labels: pieLabels,
      hole: 0.1,
      sort: false,
      textinfo: "none",
      marker: {
        colors: serviceTableRows.map((item) => item.color),
      },
      hoverlabel: {
        bgcolor: "#ffffff",
        bordercolor: "rgba(15, 52, 107, 0.14)",
        font: { color: "#001938", size: 12 },
      },
      hovertemplate:
        "<b>%{label}</b><br>" +
        "Cost=%{value:$,.2f}<br>" +
        "Share=%{percent}<extra></extra>",
      showlegend: false,
      domain: { x: [0.02, 0.98], y: [0.02, 0.98] },
    },
  ];

  const pieLayout: Partial<Layout> = {
    autosize: true,
    height: 500,
    margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    showlegend: false,
    annotations: [],
  };

  const timelineServices = Array.from(
    new Set(serviceTimeline.map((item) => item.service))
  )
    .sort((a, b) => getServiceOrder(a) - getServiceOrder(b))
    .filter((service) => visibleServices.includes(service));

  const timelineData: Partial<Data>[] = timelineServices.map((service, index) => ({
    x: serviceGroupedDates,
    y: serviceGroupedDates.map((date) => {
      const found = serviceTimeline.find(
        (item) => item.date === date && item.service === service
      );
      return found?.daily_cost ?? 0;
    }),
    type: "scatter",
    mode: "lines",
    name: getServiceShortName(service),
    stackgroup: "one",
    groupnorm: "",
    line: {
      color: getServiceColor(service),
      width: 3,
      shape: "linear",
    },
    fill: index === 0 ? "tozeroy" : "tonexty",
    hoverlabel: {
      bgcolor: "#ffffff",
      bordercolor: "rgba(15, 52, 107, 0.14)",
      font: { color: "#001938", size: 12 },
    },
    hovertemplate:
      "<b>%{fullData.name}</b><br>" +
      "Date=%{x|%b %-d, %Y}<br>" +
      "Cost (USD)=%{y:.2f}<extra></extra>",
  }));

  const timelineLayout: Partial<Layout> = {
    autosize: true,
    height: 420,
    margin: { l: 78, r: 24, t: 18, b: 72 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    showlegend: true,
    legend: {
      orientation: "h",
      x: 0,
      y: -0.2,
      font: { size: 12, color: "#001938" },
    },
    hovermode: "closest",
    dragmode: "zoom",
    xaxis: {
      title: { text: "Date", font: { size: 16, color: "#001938" } },
      type: "date",
      tickformat: "%b %-d",
      color: "#001938",
      tickfont: { size: 12 },
      showgrid: false,
      zeroline: false,
      showline: false,
    },
    yaxis: {
      title: { text: "Cost (USD)", font: { size: 16, color: "#001938" } },
      color: "#001938",
      tickfont: { size: 12 },
      tickprefix: "$",
      showgrid: true,
      gridcolor: "#00193829",
      gridwidth: 1,
      zeroline: false,
      showline: false,
      rangemode: "tozero",
    },
  };

  const downloadPng = async (
    ref: React.MutableRefObject<any>,
    filename: string,
    width: number,
    height: number
  ) => {
    if (!ref.current) return;
    try {
      await Plotly.downloadImage(ref.current, {
        format: "png",
        filename,
        width,
        height,
      } as any);
    } catch (error) {
      console.error("Plot download failed", error);
    }
  };

  const relayoutRange = async (
    ref: React.MutableRefObject<any>,
    payload: Record<string, any>
  ) => {
    if (!ref.current) return;
    try {
      await Plotly.relayout(ref.current, payload as any);
    } catch (error) {
      console.error("Plot relayout failed", error);
    }
  };

  const openFullscreen = async (
    wrapperRef: React.MutableRefObject<HTMLDivElement | null>
  ) => {
    if (!wrapperRef.current) return;

    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
        return;
      }

      await wrapperRef.current.requestFullscreen();
    } catch (error) {
      console.error("Fullscreen action failed", error);
    }
  };

  return (
    <>
      <section className="costs-hero">
        <span className="costs-hero-badge">
          <span className="costs-hero-badge-star">✦</span>
          Detailed Cost Intelligence
        </span>

        <h1>Analyze AWS spend with daily precision</h1>
        <h2>See what changed, where it grew, and why</h2>

        <p>
          Explore account-level cost movement, isolate high-impact services, and
          prepare clean exports for reporting, review, or optimization planning.
        </p>
      </section>

      <section className="dashboard-card costs-filters-card">
        <div className="card-header compact">
          <div>
            <p className="card-eyebrow">Filters</p>
            <h3>Refine cost visibility</h3>
          </div>
        </div>

        <div className="costs-filters-grid">
          <div
            className={`costs-filter-row ${preset === "Custom" ? "custom-visible" : ""}`}
          >
            <label className="costs-field">
              <CustomPresetDropdown value={preset} onChange={setPreset} />
            </label>

            {preset === "Custom" && (
              <>
                <label className="costs-field">
                  <span>Start Date</span>
                  <input
                    type="date"
                    value={customStartDate}
                    min={apiData?.available_range?.start_date ?? undefined}
                    max={
                      customEndDate ||
                      apiData?.available_range?.end_date ||
                      undefined
                    }
                    onChange={(e) => setCustomStartDate(e.target.value)}
                  />
                </label>

                <label className="costs-field">
                  <span>End Date</span>
                  <input
                    type="date"
                    value={customEndDate}
                    min={
                      customStartDate ||
                      apiData?.available_range?.start_date ||
                      undefined
                    }
                    max={apiData?.available_range?.end_date ?? undefined}
                    onChange={(e) => setCustomEndDate(e.target.value)}
                  />
                </label>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="kpi-grid">
        <article className="kpi-card kpi-card--total">
          <div className="kpi-card-top">
            <span>Total Cost</span>
            <div className="kpi-icon-bubble">
              <img
                src="/icons/dashboard/cost.png"
                alt="cost"
                className="kpi-logo-img"
              />
            </div>
          </div>
          <h3>{formatCurrencyPrecise(summary.totalCost)}</h3>
          <p className="kpi-delta up">
            {formatPercent(summary.changePct)} vs previous period
          </p>
          <div className="kpi-line" />
        </article>

        <article className="kpi-card kpi-card--avg">
          <div className="kpi-card-top">
            <span>Average Daily</span>
            <div className="kpi-icon-bubble">
              <img
                src="/icons/dashboard/average.png"
                alt="average"
                className="kpi-logo-img "
              />
            </div>
          </div>
          <h3>{formatCurrencyPrecise(summary.avgDaily)}</h3>
          <p className="kpi-delta neutral">Stable day-to-day baseline</p>
          <div className="kpi-line" />
        </article>

        <article className="kpi-card kpi-card--min">
          <div className="kpi-card-top">
            <span>Minimum Daily</span>
            <div className="kpi-icon-bubble">
              <img
                src="/icons/dashboard/down.png"
                alt="decrease"
                className="kpi-logo-img "
              />
            </div>
          </div>
          <h3>{formatCurrencyPrecise(summary.minDaily)}</h3>
          <p className="kpi-delta neutral">Lowest observed spend point</p>
          <div className="kpi-line" />
        </article>

        <article className="kpi-card kpi-card--max">
          <div className="kpi-card-top">
            <span>Maximum Daily</span>
            <div className="kpi-icon-bubble">
              <img
                src="/icons/dashboard/up.png"
                alt="increase"
                className="kpi-logo-img "
              />
            </div>
          </div>
          <h3>{formatCurrencyPrecise(summary.maxDaily)}</h3>
          <p className="kpi-delta up">Peak consumption period</p>
          <div className="kpi-line" />
        </article>
      </section>

      <section className="costs-stack">
        <article className="dashboard-card costs-chart-card">
          <div className="cost-card-head">
            <div className="cost-card-title">
              <p>Daily Trend</p>
              <div className="cost-title-inline">
                <h3>Daily costs</h3>
                <span className="cost-title-pill">{presetLabel}</span>
                <span className="cost-title-pill">{dateRangeLabel}</span>
              </div>
            </div>

            <ChartToolbar
              onCsvDownload={() =>
                exportCsv(
                  `daily_costs_${presetLabel
                    .replace(/\s+/g, "_")
                    .toLowerCase()}.csv`,
                  filteredDailyCosts.map((item) => item)
                )
              }
              onPngDownload={() =>
                downloadPng(dailyGraphRef, "daily_costs", 1400, 700)
              }
              onZoomIn={() => {
                const currentX = dailyGraphRef.current?.layout?.xaxis?.range as
                  | [string, string]
                  | undefined;
                const currentY = dailyGraphRef.current?.layout?.yaxis?.range as
                  | [number, number]
                  | undefined;

                const nextX = zoomDateRange(currentX, dailyXValues, 0.7);
                const nextY = zoomNumberRange(
                  currentY,
                  dailyPaddedMinY,
                  dailyPaddedMaxY,
                  0.7
                );

                relayoutRange(dailyGraphRef, {
                  "xaxis.range": [nextX[0], nextX[1]],
                  "yaxis.range": [nextY[0], nextY[1]],
                });
              }}
              onZoomOut={() => {
                const currentX = dailyGraphRef.current?.layout?.xaxis?.range as
                  | [string, string]
                  | undefined;
                const currentY = dailyGraphRef.current?.layout?.yaxis?.range as
                  | [number, number]
                  | undefined;

                const nextX = zoomDateRange(currentX, dailyXValues, 1.35);
                const nextY = zoomNumberRange(
                  currentY,
                  dailyPaddedMinY,
                  dailyPaddedMaxY,
                  1.35
                );

                relayoutRange(dailyGraphRef, {
                  "xaxis.range": [nextX[0], nextX[1]],
                  "yaxis.range": [nextY[0], nextY[1]],
                });
              }}
              onReset={() =>
                relayoutRange(dailyGraphRef, {
                  "xaxis.autorange": true,
                  "yaxis.autorange": true,
                })
              }
              onFullscreen={() => openFullscreen(dailyWrapperRef)}
            />
          </div>

          <div
            className="cost-plotly-shell daily-main-plot-shell"
            ref={dailyWrapperRef}
          >
            <div className="cost-plotly-chart-wrap short daily-main-plot-wrap">
              <Plot
                data={dailyData}
                layout={dailyLayout as any}
                config={commonPlotConfig}
                onInitialized={(_, graphDiv) => {
                  dailyGraphRef.current = graphDiv;
                }}
                onUpdate={(_, graphDiv) => {
                  dailyGraphRef.current = graphDiv;
                }}
                useResizeHandler
                className="cost-plotly-chart daily-main-plot"
              />
            </div>
          </div>
        </article>

        <div className="costs-row-two">
          <article className="dashboard-card costs-breakdown-card">
            <div className="cost-card-head">
              <div className="cost-card-title">
                <p>Cost Breakdown</p>
                <h3>Cost breakdown by service</h3>
              </div>

              <ChartToolbar
                onCsvDownload={() =>
                  exportCsv(
                    "cost_breakdown_by_service.csv",
                    serviceTableRows.map((item) => ({
                      service: item.service,
                      total_cost: item.total_cost,
                      percentage: item.percent,
                    }))
                  )
                }
                onPngDownload={() =>
                  downloadPng(barGraphRef, "cost_breakdown_by_service", 1300, 700)
                }
                onZoomIn={() => {
                  const currentX = barGraphRef.current?.layout?.xaxis?.range as
                    | [number, number]
                    | undefined;
                  const nextX = zoomNumberRange(currentX, 0, barPaddedMaxX, 0.7);

                  relayoutRange(barGraphRef, {
                    "xaxis.range": [nextX[0], nextX[1]],
                  });
                }}
                onZoomOut={() => {
                  const currentX = barGraphRef.current?.layout?.xaxis?.range as
                    | [number, number]
                    | undefined;
                  const nextX = zoomNumberRange(currentX, 0, barPaddedMaxX, 1.35);

                  relayoutRange(barGraphRef, {
                    "xaxis.range": [Math.max(0, nextX[0]), nextX[1]],
                  });
                }}
                onReset={() =>
                  relayoutRange(barGraphRef, {
                    "xaxis.autorange": true,
                    "yaxis.autorange": true,
                  })
                }
                onFullscreen={() => openFullscreen(barWrapperRef)}
              />
            </div>

            <div className="cost-plotly-shell" ref={barWrapperRef}>
              <div className="cost-plotly-chart-wrap short">
                <Plot
                  data={barData}
                  layout={barLayout as any}
                  config={commonPlotConfig}
                  onInitialized={(_, graphDiv) => {
                    barGraphRef.current = graphDiv;
                  }}
                  onUpdate={(_, graphDiv) => {
                    barGraphRef.current = graphDiv;
                  }}
                  useResizeHandler
                  className="cost-plotly-chart"
                />
              </div>
            </div>
          </article>

          <article className="dashboard-card costs-distribution-card">
            <div className="cost-card-head">
              <div className="cost-card-title">
                <p>Cost Distribution</p>
                <h3>Cost distribution</h3>
              </div>

              <ChartToolbar
                onCsvDownload={() =>
                  exportCsv(
                    "cost_distribution.csv",
                    serviceTableRows.map((item) => ({
                      service: item.service,
                      total_cost: item.total_cost,
                      percentage: item.percent,
                    }))
                  )
                }
                onPngDownload={() =>
                  downloadPng(pieGraphRef, "cost_distribution", 1200, 700)
                }
                onZoomIn={() => { }}
                onZoomOut={() => { }}
                onReset={() => { }}
                onFullscreen={() => openFullscreen(pieWrapperRef)}
              />
            </div>

            <div className="cost-distribution-total">
              {formatCurrency(distributionTotal)}
            </div>

            <div className="cost-distribution-total-label">Total cost</div>

            <div className="cost-distribution-layout" ref={pieWrapperRef}>
              <div className="cost-distribution-chart">
                <div className="cost-plotly-shell">
                  <div className="cost-plotly-chart-wrap pie-large">
                    <Plot
                      data={pieData}
                      layout={pieLayout as any}
                      config={commonPlotConfig}
                      onInitialized={(_, graphDiv) => {
                        pieGraphRef.current = graphDiv;
                      }}
                      onUpdate={(_, graphDiv) => {
                        pieGraphRef.current = graphDiv;
                      }}
                      useResizeHandler
                      className="cost-plotly-chart"
                    />
                  </div>
                </div>
              </div>

              <div className="cost-distribution-side">
                <div className="cost-distribution-list">
                  {serviceTableRows.map((row) => (
                    <div key={row.service} className="cost-distribution-item">
                      <div className="cost-distribution-service">
                        <span
                          className="cost-distribution-dot"
                          style={{ background: row.color }}
                        />
                        <span className="cost-distribution-name">
                          {getServiceDisplayName(row.service)}
                        </span>
                      </div>

                      <span className="cost-distribution-share">
                        {row.percent}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>
        </div>

        <article className="dashboard-card costs-timeline-card">
          <div className="service-toolbar-wrap">
            <div className="cost-card-head" style={{ marginBottom: 0 }}>
              <div className="cost-card-title">
                <p>Service Timeline across selected dates</p>
                <h3>Service costs over time</h3>
              </div>

              <ChartToolbar
                onCsvDownload={() =>
                  exportCsv(
                    "service_costs_over_time.csv",
                    serviceTimeline
                      .filter((item) => visibleServices.includes(item.service))
                      .map((item) => ({
                        date: item.date,
                        service: item.service,
                        daily_cost: item.daily_cost,
                      }))
                  )
                }
                onPngDownload={() =>
                  downloadPng(
                    serviceGraphRef,
                    "service_costs_over_time",
                    1500,
                    760
                  )
                }
                onZoomIn={() => {
                  const currentX = serviceGraphRef.current?.layout?.xaxis?.range as
                    | [string, string]
                    | undefined;
                  const currentY = serviceGraphRef.current?.layout?.yaxis?.range as
                    | [number, number]
                    | undefined;

                  const nextX = zoomDateRange(currentX, serviceGroupedDates, 0.7);
                  const nextY = zoomNumberRange(
                    currentY,
                    servicePaddedMinY,
                    servicePaddedMaxY,
                    0.7
                  );

                  relayoutRange(serviceGraphRef, {
                    "xaxis.range": [nextX[0], nextX[1]],
                    "yaxis.range": [nextY[0], nextY[1]],
                  });
                }}
                onZoomOut={() => {
                  const currentX = serviceGraphRef.current?.layout?.xaxis?.range as
                    | [string, string]
                    | undefined;
                  const currentY = serviceGraphRef.current?.layout?.yaxis?.range as
                    | [number, number]
                    | undefined;

                  const nextX = zoomDateRange(currentX, serviceGroupedDates, 1.35);
                  const nextY = zoomNumberRange(
                    currentY,
                    servicePaddedMinY,
                    servicePaddedMaxY,
                    1.35
                  );

                  relayoutRange(serviceGraphRef, {
                    "xaxis.range": [nextX[0], nextX[1]],
                    "yaxis.range": [nextY[0], nextY[1]],
                  });
                }}
                onReset={() =>
                  relayoutRange(serviceGraphRef, {
                    "xaxis.autorange": true,
                    "yaxis.autorange": true,
                  })
                }
                onFullscreen={() => openFullscreen(serviceWrapperRef)}
              />
            </div>

            <div className="service-selector-row">
              {availableTimelineServices.map((service) => {
                const active = visibleServices.includes(service);
                return (
                  <button
                    key={service}
                    type="button"
                    className={`service-chip ${active ? "active" : ""}`}
                    onClick={() => toggleVisibleService(service)}
                    onDoubleClick={() => showOnlyService(service)}
                    style={
                      active
                        ? {
                          borderColor: SERVICE_COLORS[service] || "#1f66ff",
                          background: `${SERVICE_COLORS[service] || "#1f66ff"}22`,
                        }
                        : undefined
                    }
                  >
                    <span
                      className="service-chip-dot"
                      style={{ background: SERVICE_COLORS[service] || "#94a3b8" }}
                    />
                    <span>{service}</span>
                  </button>
                );
              })}

              <button
                type="button"
                className="service-show-all-btn"
                onClick={resetVisibleServices}
              >
                Show All
              </button>
            </div>

            <p className="service-selector-note">
              Single click = show/hide service. Double click = show this service only.
            </p>
          </div>

          <div className="cost-plotly-shell" ref={serviceWrapperRef}>
            <div className="cost-plotly-chart-wrap">
              <Plot
                data={timelineData}
                layout={timelineLayout as any}
                config={commonPlotConfig}
                onInitialized={(_, graphDiv) => {
                  serviceGraphRef.current = graphDiv;
                }}
                onUpdate={(_, graphDiv) => {
                  serviceGraphRef.current = graphDiv;
                }}
                useResizeHandler
                className="cost-plotly-chart"
              />
            </div>
          </div>
        </article>

        <article className="dashboard-card costs-table-card">
          <div className="cost-card-head">
            <div className="cost-card-title">
              <p>Service Cost Details</p>
              <h3>Detailed breakdown table</h3>
            </div>

            <button
              type="button"
              className="card-link-btn"
              onClick={() =>
                exportCsv(
                  "service_costs_export.csv",
                  serviceTableRows.map((item) => ({
                    service: item.service,
                    total_cost: item.total_cost,
                    percentage: item.percent,
                  }))
                )
              }
            >
              Export Table
            </button>
          </div>

          <div className="cost-table-wrap">
            <table className="cost-table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>Total Cost</th>
                  <th>% of Visible Total</th>
                  <th>Share</th>
                </tr>
              </thead>
              <tbody>
                {serviceTableRows.map((row) => (
                  <tr key={row.service}>
                    <td>
                      <div className="cost-table-service">
                        <span
                          className="cost-table-dot"
                          style={{ background: row.color }}
                        />
                        {row.service}
                      </div>
                    </td>
                    <td>{formatCurrencyPrecise(row.total_cost)}</td>
                    <td>{row.percent}%</td>
                    <td>
                      <div className="cost-inline-bar">
                        <div
                          className="cost-inline-bar-fill"
                          style={{
                            width: `${row.percent}%`,
                            minWidth: row.percent > 0 ? "8px" : "0px",
                            background: row.color,
                          }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="dashboard-card costs-records-card">
          <div className="cost-card-head">
            <div className="cost-card-title">
              <p>Daily Records</p>
              <h3>Raw daily cost log</h3>
            </div>

            <div className="cost-records-actions">
              <button
                type="button"
                className="card-link-btn"
                onClick={() =>
                  exportCsv(
                    "daily_records_export.csv",
                    filteredDailyCosts.map((item) => ({
                      date: item.date,
                      total_cost: item.total_cost,
                    }))
                  )
                }
              >
                Export Table
              </button>

              <label className="cost-toggle">
                <input
                  type="checkbox"
                  checked={showRecords}
                  onChange={() => setShowRecords((prev) => !prev)}
                />
                <span>Show records</span>
              </label>
            </div>
          </div>

          {showRecords ? (
            <div className="cost-table-wrap slim">
              <table className="cost-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Total Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDailyCosts.map((item) => (
                    <tr key={item.date}>
                      <td>{item.date}</td>
                      <td>{formatCurrencyPrecise(item.total_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="cost-empty-state">
              <div>
                <strong>Daily records are collapsed</strong>
                <p>Enable the toggle to inspect raw daily entries before export.</p>
              </div>
            </div>
          )}
        </article>
      </section>
    </>
  );
}

