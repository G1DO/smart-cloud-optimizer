"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import dynamic from "next/dynamic";
import Plotly from "plotly.js-dist-min";
import type { Config, Data, Layout } from "plotly.js";
import "../home/dashboard.css";
import "./forecasts.css";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type ModelType = "Prophet" | "SARIMAX" | "ETS" | "Seasonal Naive" | "Naive";

type HistoricalPoint = {
  date: string;
  total_cost: number;
};

type ForecastPoint = {
  date: string;
  forecast: number;
  lower: number;
  upper: number;
};

type ForecastSummary = {
  model: string;
  horizon: number;
  historical_days: number;
  predicted_total: number;
  avg_daily_forecast: number;
  min_forecast: number;
  max_forecast: number;
  historical_avg_daily: number;
  vs_historical_pct: number | null;
};

type ComparisonRow = {
  model: string;
  avg_daily_forecast: number | null;
  total_forecast: number | null;
  historical_avg_daily: number | null;
  vs_historical_pct: number | null;
};

type ForecastApiResponse = {
  summary: ForecastSummary;
  historical: HistoricalPoint[];
  forecast: ForecastPoint[];
};

type ComparisonApiResponse = {
  comparison: ComparisonRow[];
};

const MODEL_OPTIONS: { value: ModelType; subtitle: string }[] = [
  { value: "Prophet", subtitle: "Balanced trend forecast" },
  { value: "SARIMAX", subtitle: "Seasonal statistical model" },
  { value: "ETS", subtitle: "Level and trend smoothing" },
  { value: "Seasonal Naive", subtitle: "Repeats past seasonal pattern" },
  { value: "Naive", subtitle: "Simple carry-forward baseline" },
];

const HORIZON_OPTIONS: { value: number; subtitle: string }[] = [
  { value: 7, subtitle: "Short outlook" },
  { value: 14, subtitle: "2-week view" },
  { value: 30, subtitle: "Monthly planning" },
  { value: 60, subtitle: "Mid-range estimate" },
  { value: 90, subtitle: "Longer horizon" },
];

const DEFAULT_USER_ID = "aws-SYNTHETIC-001";
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

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

const MODEL_COLORS: Record<string, string> = {
  Prophet: "#1f79ffc6",
  SARIMAX: "#7c3aedc6",
  ETS: "#10b981c6",
  "Seasonal Naive": "#f59e0bc6",
  Naive: "#64748bc6",
};

function getModelColor(model: string) {
  return MODEL_COLORS[model] || "#1f66ff";
}

function getModelCardClass(model: string) {
  switch (model) {
    case "Prophet":
      return "forecast-model-pill--prophet";
    case "SARIMAX":
      return "forecast-model-pill--sarimax";
    case "ETS":
      return "forecast-model-pill--ets";
    case "Seasonal Naive":
      return "forecast-model-pill--seasonal-naive";
    case "Naive":
      return "forecast-model-pill--naive";
    default:
      return "";
  }
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

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function exportCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;

  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map((row) =>
      headers
        .map((header) => {
          const value = row[header];
          const normalized =
            value == null
              ? ""
              : String(value).replace(/"/g, '""').replace(/\n/g, " ");
          return `"${normalized}"`;
        })
        .join(",")
    ),
  ].join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function zoomDateRange(
  currentRange: [string, string] | undefined,
  fallbackDates: string[],
  factor: number
): [string, string] {
  const parseDate = (value: string) => new Date(value).getTime();

  let start: number;
  let end: number;

  if (
    currentRange &&
    currentRange[0] &&
    currentRange[1] &&
    !Number.isNaN(parseDate(currentRange[0])) &&
    !Number.isNaN(parseDate(currentRange[1]))
  ) {
    start = parseDate(currentRange[0]);
    end = parseDate(currentRange[1]);
  } else {
    const timestamps = fallbackDates
      .map(parseDate)
      .filter((value) => !Number.isNaN(value));

    if (!timestamps.length) {
      const now = Date.now();
      return [
        new Date(now - 7 * 86400000).toISOString(),
        new Date(now).toISOString(),
      ];
    }

    start = Math.min(...timestamps);
    end = Math.max(...timestamps);
  }

  const mid = (start + end) / 2;
  const half = ((end - start) / 2) * factor;

  return [new Date(mid - half).toISOString(), new Date(mid + half).toISOString()];
}

function zoomNumberRange(
  currentRange: [number, number] | undefined,
  fallbackMin: number,
  fallbackMax: number,
  factor: number
): [number, number] {
  let min = currentRange?.[0] ?? fallbackMin;
  let max = currentRange?.[1] ?? fallbackMax;

  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    min = fallbackMin;
    max = fallbackMax;
  }

  const mid = (min + max) / 2;
  const half = ((max - min) / 2) * factor;

  return [mid - half, mid + half];
}

function getTrendLabel(current: number, previous: number) {
  const diff = current - previous;
  const threshold = Math.max(0.01, previous * 0.01);

  if (diff > threshold) {
    return { label: "Upward", className: "up" };
  }
  if (diff < -threshold) {
    return { label: "Downward", className: "down" };
  }
  return { label: "Stable", className: "flat" };
}

function ToolbarButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void | Promise<void>;
  disabled?: boolean;
  children: ReactNode;
}) {
  const handleClick = () => {
    void Promise.resolve(onClick()).catch((error) => {
      console.error(`${label} action failed`, error);
    });
  };

  return (
    <button
      type="button"
      className="forecast-chart-tool-btn"
      onClick={handleClick}
      disabled={disabled}
      title={label}
      aria-label={label}
    >
      {children}
    </button>
  );
}

function ChartToolbar({
  disabled,
  onCsvDownload,
  onPngDownload,
  onZoomIn,
  onZoomOut,
  onReset,
  onFullscreen,
}: {
  disabled?: boolean;
  onCsvDownload: () => void;
  onPngDownload: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onFullscreen: () => void;
}) {
  return (
    <div className="forecast-chart-tools">
      <ToolbarButton label="Download CSV" onClick={onCsvDownload} disabled={disabled}>
        <img
          src="/icons/imagebar/download.png"
          alt="download"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Download plot as PNG" onClick={onPngDownload} disabled={disabled}>
        <img
          src="/icons/imagebar/camera.png"
          alt="camera"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Zoom in" onClick={onZoomIn} disabled={disabled}>
        <img
          src="/icons/imagebar/zoomin.png"
          alt="zoomin"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Zoom out" onClick={onZoomOut} disabled={disabled}>
        <img
          src="/icons/imagebar/zoomout.png"
          alt="zoomout"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Reset axes" onClick={onReset} disabled={disabled}>
        <img
          src="/icons/imagebar/reset.png"
          alt="reset"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Full screen" onClick={onFullscreen} disabled={disabled}>
        <img
          src="/icons/imagebar/full.png"
          alt="full"
          className="bar-icon-img"
        />
      </ToolbarButton>
    </div>
  );
}

function StatusBanner({
  type,
  message,
}: {
  type: "info" | "success" | "error";
  message: string;
}) {
  const icon = type === "success" ? "✓" : type === "error" ? "!" : "⋯";

  return (
    <div className={`forecast-status-banner forecast-status-banner--${type}`}>
      <span className="forecast-status-icon">{icon}</span>
      <span>{message}</span>
    </div>
  );
}

function CustomForecastDropdown<T extends string | number>({
  value,
  options,
  label,
  onChange,
  disabled,
}: {
  value: T;
  options: { value: T; subtitle: string }[];
  label: string;
  onChange: (value: T) => void;
  disabled?: boolean;
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

  const selectedOption =
    options.find((option) => option.value === value) ?? options[0];

  return (
    <div
      className={`forecasts-dropdown ${open ? "open" : ""} ${disabled ? "disabled" : ""
        }`}
      ref={dropdownRef}
    >
      <button
        type="button"
        className="forecasts-dropdown-trigger"
        onClick={() => !disabled && setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
      >
        <span className="forecasts-dropdown-value-wrap">
          <span className="forecasts-dropdown-value-label">{label}</span>
          <span className="forecasts-dropdown-value">{selectedOption.value}</span>
        </span>

        <svg
          className="forecasts-dropdown-arrow"
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
        <div className="forecasts-dropdown-menu" role="listbox">
          {options.map((option) => {
            const active = option.value === value;

            return (
              <button
                key={String(option.value)}
                type="button"
                className={`forecasts-dropdown-option ${active ? "active" : ""}`}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                <span className="forecasts-dropdown-option-main">
                  <span className="forecasts-dropdown-option-title">
                    {option.value}
                  </span>
                  <span className="forecasts-dropdown-option-subtitle">
                    {option.subtitle}
                  </span>
                </span>

                <svg
                  className="forecasts-dropdown-check"
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

function KpiSkeletonCard({ type }: { type: string }) {
  return (
    <article className={`forecast-kpi-card ${type}`}>
      <div className="forecast-kpi-top">
        <span className="forecast-skeleton forecast-skeleton-text short" />
        <span className="forecast-skeleton forecast-skeleton-circle" />
      </div>

      <div className="forecast-skeleton forecast-skeleton-value" />
      <div className="forecast-skeleton forecast-skeleton-text medium" />
      <div className="forecast-kpi-line" />
    </article>
  );
}

export default function ForecastsPage() {
  const [forecastHorizon, setForecastHorizon] = useState<number>(30);
  const [modelChoice, setModelChoice] = useState<ModelType>("Prophet");
  const [showModelComparison, setShowModelComparison] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const [workspaceState, setWorkspaceState] =
    useState<WorkspaceDataState>(EMPTY_WORKSPACE_STATE);

  const [historicalData, setHistoricalData] = useState<HistoricalPoint[]>([]);
  const [forecastData, setForecastData] = useState<ForecastPoint[]>([]);
  const [comparisonRows, setComparisonRows] = useState<ComparisonRow[]>([]);
  const [summary, setSummary] = useState<ForecastSummary | null>(null);

  const [loading, setLoading] = useState(true);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusType, setStatusType] = useState<"info" | "success" | null>(null);

  const comparisonCacheRef = useRef<Record<number, ComparisonRow[]>>({});

  const recentHistorical = useMemo(() => historicalData.slice(-90), [historicalData]);

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
    if (!workspaceState.isDemoMode && !workspaceState.hasConnectedAccount) {
      setLoading(false);
      setError(null);
      setHistoricalData([]);
      setForecastData([]);
      setComparisonRows([]);
      setSummary(null);
      setStatusType(null);
      setStatusMessage(null);
      return;
    }

    if (!workspaceState.userId) {
      setLoading(false);
      setError(null);
      setHistoricalData([]);
      setForecastData([]);
      setComparisonRows([]);
      setSummary(null);
      setStatusType(null);
      setStatusMessage(null);
      return;
    }

    const controller = new AbortController();

    async function loadForecast() {
      setLoading(true);
      setError(null);
      setStatusType("info");
      setStatusMessage(
        `Running ${modelChoice} forecast for the next ${forecastHorizon} days...`
      );

      try {
        const url = new URL(`${API_BASE}/api/forecast`);
        url.searchParams.set("user_id", workspaceState.userId);
        url.searchParams.set("model", modelChoice);
        url.searchParams.set("horizon", String(forecastHorizon));

        const response = await fetch(url.toString(), {
          method: "GET",
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          let message = "Failed to load forecast data.";
          try {
            const err = await response.json();
            if (err?.detail) message = String(err.detail);
          } catch {
            //
          }
          throw new Error(message);
        }

        const data: ForecastApiResponse = await response.json();

        setHistoricalData(Array.isArray(data.historical) ? data.historical : []);
        setForecastData(Array.isArray(data.forecast) ? data.forecast : []);
        setSummary(data.summary ?? null);

        setStatusType("success");
        setStatusMessage(`Forecast ready using ${modelChoice}`);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;

        const message =
          (err as Error).message ||
          "Something went wrong while loading forecast data.";

        setError(message);
        setHistoricalData([]);
        setForecastData([]);
        setSummary(null);
        setStatusType(null);
        setStatusMessage(null);
      } finally {
        setLoading(false);
      }
    }

    loadForecast();

    return () => controller.abort();
  }, [
    forecastHorizon,
    modelChoice,
    workspaceState.userId,
    workspaceState.isDemoMode,
    workspaceState.hasConnectedAccount,
  ]);

  useEffect(() => {
    if (!showModelComparison || error) return;

    if (!workspaceState.isDemoMode && !workspaceState.hasConnectedAccount) {
      setComparisonRows([]);
      setComparisonLoading(false);
      return;
    }

    if (!workspaceState.userId) {
      setComparisonRows([]);
      setComparisonLoading(false);
      return;
    }

    const cached = comparisonCacheRef.current[forecastHorizon];
    if (cached?.length) {
      setComparisonRows(cached);
      setComparisonLoading(false);
      return;
    }

    const controller = new AbortController();

    async function loadComparison() {
      setComparisonLoading(true);

      try {
        const url = new URL(`${API_BASE}/api/forecast/compare`);
        url.searchParams.set("user_id", workspaceState.userId);
        url.searchParams.set("horizon", String(forecastHorizon));

        const response = await fetch(url.toString(), {
          method: "GET",
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          let message = "Failed to load model comparison.";
          try {
            const err = await response.json();
            if (err?.detail) message = String(err.detail);
          } catch {
            //
          }
          throw new Error(message);
        }

        const data: ComparisonApiResponse = await response.json();
        const rows = Array.isArray(data.comparison) ? data.comparison : [];

        comparisonCacheRef.current[forecastHorizon] = rows;
        setComparisonRows(rows);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setComparisonRows([]);
      } finally {
        setComparisonLoading(false);
      }
    }

    loadComparison();

    return () => controller.abort();
  }, [
    showModelComparison,
    forecastHorizon,
    error,
    workspaceState.userId,
    workspaceState.isDemoMode,
    workspaceState.hasConnectedAccount,
  ]);

  const rankedComparisonRows = useMemo(() => {
    return comparisonRows.map((row, index) => ({
      ...row,
      rank: index + 1,
    }));
  }, [comparisonRows]);

  const detailsRows = useMemo(() => {
    return forecastData.map((row, index) => {
      const previous =
        index === 0
          ? recentHistorical[recentHistorical.length - 1]?.total_cost ?? row.forecast
          : forecastData[index - 1]?.forecast ?? row.forecast;

      const trend = getTrendLabel(row.forecast, previous);

      return {
        ...row,
        trend,
      };
    });
  }, [forecastData, recentHistorical]);

  const combinedDates = [
    ...recentHistorical.map((row) => row.date),
    ...forecastData.map((row) => row.date),
  ];

  const combinedYValuesRaw = [
    ...recentHistorical.map((row) => row.total_cost),
    ...forecastData.map((row) => row.forecast),
    ...forecastData.map((row) => row.lower),
    ...forecastData.map((row) => row.upper),
  ];

  const combinedYValues = combinedYValuesRaw.length ? combinedYValuesRaw : [0, 100];
  const yMin = Math.min(...combinedYValues);
  const yMax = Math.max(...combinedYValues);
  const paddedMinY = Math.max(
    0,
    yMin - Math.max(15, Math.round((yMax - yMin || 1) * 0.16))
  );
  const paddedMaxY =
    yMax + Math.max(15, Math.round((yMax - yMin || 1) * 0.16));

  const forecastGraphRef = useRef<any>(null);
  const forecastWrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const updateDarkMode = () => {
      const shell =
        forecastWrapperRef.current?.closest(".dashboard-shell") ??
        document.querySelector(".dashboard-shell");

      const darkDetected =
        shell?.classList.contains("dashboard-dark") ||
        document.documentElement.classList.contains("dark") ||
        document.body.classList.contains("dark");

      setIsDark(Boolean(darkDetected));
    };

    updateDarkMode();

    const shell =
      forecastWrapperRef.current?.closest(".dashboard-shell") ??
      document.querySelector(".dashboard-shell");

    const observer = new MutationObserver(() => {
      updateDarkMode();
    });

    if (shell) {
      observer.observe(shell, {
        attributes: true,
        attributeFilter: ["class"],
      });
    }

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, []);

  const axisColor = isDark ? "#dbeafe" : "#001938";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.22)" : "#00193841";
  const legendColor = isDark ? "#dbeafe" : "#003638";
  const hoverBg = isDark ? "#0f172a" : "#ffffff";
  const hoverBorder = isDark
    ? "rgba(148, 163, 184, 0.24)"
    : "rgba(15, 52, 107, 0.14)";
  const hoverText = isDark ? "#e2e8f0" : "#4c5d79";

  const commonPlotConfig: Partial<Config> = {
    responsive: true,
    displayModeBar: false,
    displaylogo: false,
    scrollZoom: true,
  };

  const chartData: Partial<Data>[] = [
    {
      x: forecastData.map((row) => row.date),
      y: forecastData.map((row) => row.upper),
      type: "scatter",
      mode: "lines",
      line: { width: 0 },
      hoverinfo: "skip",
      showlegend: false,
      name: "Upper",
    },
    {
      x: forecastData.map((row) => row.date),
      y: forecastData.map((row) => row.lower),
      type: "scatter",
      mode: "lines",
      fill: "tonexty",
      fillcolor: "rgba(245, 158, 11, 0.18)",
      line: { width: 0 },
      hoverlabel: {
        bgcolor: hoverBg,
        bordercolor: hoverBorder,
        font: { color: hoverText, size: 12 },
      },
      hovertemplate:
        "<b>Confidence Interval</b><br>" +
        "Date=%{x|%b %-d, %Y}<br>" +
        "Lower Bound=%{y:.2f}<extra></extra>",
      name: "Confidence Interval",
    },
    {
      x: recentHistorical.map((row) => row.date),
      y: recentHistorical.map((row) => row.total_cost),
      type: "scatter",
      mode: "lines",
      name: "Historical",
      line: { color: "#2d6cf6", width: 4 },
      hoverlabel: {
        bgcolor: hoverBg,
        bordercolor: hoverBorder,
        font: { color: hoverText, size: 12 },
      },
      hovertemplate:
        "<b>Historical</b><br>" +
        "Date=%{x|%b %-d, %Y}<br>" +
        "Cost (USD)=%{y:.2f}<extra></extra>",
    },
    {
      x: forecastData.map((row) => row.date),
      y: forecastData.map((row) => row.forecast),
      type: "scatter",
      mode: "lines",
      name: "Forecast",
      line: { color: "#f59e0b", width: 4, dash: "dash" },
      hoverlabel: {
        bgcolor: hoverBg,
        bordercolor: hoverBorder,
        font: { color: hoverText, size: 12 },
      },
      hovertemplate:
        "<b>Forecast</b><br>" +
        "Date=%{x|%b %-d, %Y}<br>" +
        "Cost (USD)=%{y:.2f}<extra></extra>",
    },
  ];

  const chartLayout: Partial<Layout> = {
    autosize: true,
    height: 470,
    margin: { l: 78, r: 24, t: 18, b: 72 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    hovermode: "x unified",
    dragmode: "zoom",
    legend: {
      orientation: "h",
      x: 0,
      y: 1.12,
      font: { size: 12, color: legendColor },
    },
    xaxis: {
      title: { text: "Date", font: { size: 16, color: axisColor } },
      type: "date",
      tickformat: "%b %-d",
      color: axisColor,
      tickfont: { size: 12, color: axisColor },
      showgrid: false,
      zeroline: false,
      showline: false,
    },
    yaxis: {
      title: { text: "Cost (USD)", font: { size: 16, color: axisColor } },
      color: axisColor,
      tickfont: { size: 12, color: axisColor },
      tickprefix: "$",
      showgrid: true,
      gridcolor: gridColor,
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

  const safeSummary = summary ?? {
    model: modelChoice,
    horizon: forecastHorizon,
    historical_days: historicalData.length,
    predicted_total: 0,
    avg_daily_forecast: 0,
    min_forecast: 0,
    max_forecast: 0,
    historical_avg_daily: 0,
    vs_historical_pct: 0,
  };

  const avgDeltaClass =
    (safeSummary.vs_historical_pct ?? 0) > 0
      ? "up"
      : (safeSummary.vs_historical_pct ?? 0) < 0
        ? "down"
        : "neutral";

  return (
    <div className="forecasts-page">
      <section className="forecasts-hero">
        <span className="forecasts-hero-badge">
          <span className="forecasts-hero-badge-star">✦</span>
          Predictive Cost Intelligence
        </span>

        <h1>Forecast cloud spend before it surprises you</h1>
        <h2>Model future cost movement with clear visual confidence</h2>

        <p>
          Explore historical behavior, predicted totals, confidence intervals,
          and ranked model snapshots in one clean forecasting workspace.
        </p>
      </section>

      <section className="dashboard-card forecasts-filters-card">
        <div className="card-header compact">
          <div>
            <p className="card-eyebrow">Forecast Configuration</p>
            <h3>Choose forecast model and horizon</h3>
          </div>
        </div>

        <div className="forecasts-filters-grid">
          <label className="forecasts-field">
            <CustomForecastDropdown
              value={forecastHorizon}
              options={HORIZON_OPTIONS}
              label="Forecast horizon"
              onChange={setForecastHorizon}
              disabled={loading}
            />
          </label>

          <label className="forecasts-field">
            <CustomForecastDropdown
              value={modelChoice}
              options={MODEL_OPTIONS}
              label="Forecast model"
              onChange={(value) => setModelChoice(value)}
              disabled={loading}
            />
          </label>
        </div>

        <p className="forecasts-config-note">
          Current selection: <strong>{modelChoice}</strong> •{" "}
          <strong>{forecastHorizon} days</strong>
        </p>
      </section>

      {statusMessage && !error && statusType && (
        <StatusBanner type={statusType} message={statusMessage} />
      )}

      {error && <StatusBanner type="error" message={error} />}

      <section className="forecast-kpi-grid">
        {loading ? (
          <>
            <KpiSkeletonCard type="forecast-kpi-card--total" />
            <KpiSkeletonCard type="forecast-kpi-card--avg" />
            <KpiSkeletonCard type="forecast-kpi-card--min" />
            <KpiSkeletonCard type="forecast-kpi-card--max" />
          </>
        ) : (
          <>
            <article className="forecast-kpi-card forecast-kpi-card--total">
              <div className="forecast-kpi-top">
                <span>Predicted Total</span>
                <div className="forecast-kpi-icon">
                  <img
                    src="/icons/dashboard/predict.png"
                    alt="predict"
                    className="forecast-kpi-logo"
                  />
                </div>
              </div>
              <h3>{formatCurrencyPrecise(safeSummary.predicted_total)}</h3>
              <p className="forecast-kpi-delta neutral">
                Forecasted for next {forecastHorizon} days
              </p>
              <div className="forecast-kpi-line" />
            </article>

            <article className="forecast-kpi-card forecast-kpi-card--avg">
              <div className="forecast-kpi-top">
                <span>Average Daily</span>
                <div className="forecast-kpi-icon">
                  <img
                    src="/icons/dashboard/average.png"
                    alt="average"
                    className="forecast-kpi-logo"
                  />
                </div>
              </div>
              <h3>{formatCurrencyPrecise(safeSummary.avg_daily_forecast)}</h3>
              <p className={`forecast-kpi-delta ${avgDeltaClass}`}>
                {formatPercent(safeSummary.vs_historical_pct ?? 0)} vs historical average
              </p>
              <div className="forecast-kpi-line" />
            </article>

            <article className="forecast-kpi-card forecast-kpi-card--min">
              <div className="forecast-kpi-top">
                <span>Minimum Daily</span>
                <div className="forecast-kpi-icon">
                  <img
                    src="/icons/dashboard/down.png"
                    alt="decrease"
                    className="forecast-kpi-logo"
                  />
                </div>
              </div>
              <h3>{formatCurrencyPrecise(safeSummary.min_forecast)}</h3>
              <p className="forecast-kpi-delta neutral">Lowest predicted daily cost</p>
              <div className="forecast-kpi-line" />
            </article>

            <article className="forecast-kpi-card forecast-kpi-card--max">
              <div className="forecast-kpi-top">
                <span>Maximum Daily</span>
                <div className="forecast-kpi-icon">
                  <img
                    src="/icons/dashboard/up.png"
                    alt="increase"
                    className="forecast-kpi-logo"
                  />
                </div>
              </div>
              <h3>{formatCurrencyPrecise(safeSummary.max_forecast)}</h3>
              <p className="forecast-kpi-delta neutral">Highest predicted daily cost</p>
              <div className="forecast-kpi-line" />
            </article>
          </>
        )}
      </section>

      <section className="forecasts-stack">
        <article className="dashboard-card forecast-chart-card">
          <div className="forecast-card-head">
            <div className="forecast-card-title">
              <p className="forecast-card-kicker">Forecast View</p>
              <div className="forecast-title-inline">
                <h3>Historical vs predicted costs</h3>
                <span className="forecast-title-pill">{modelChoice}</span>
                <span className="forecast-title-pill">{forecastHorizon} Days</span>
              </div>
              <p className="forecast-card-subline">
                Last 90 historical days with predicted line and confidence interval
              </p>
            </div>

            <ChartToolbar
              disabled={loading || !forecastData.length}
              onCsvDownload={() =>
                exportCsv(
                  `forecast_${modelChoice
                    .replace(/\s+/g, "_")
                    .toLowerCase()}_${forecastHorizon}days.csv`,
                  forecastData.map((row) => ({
                    date: row.date,
                    forecast: row.forecast,
                    lower: row.lower,
                    upper: row.upper,
                  }))
                )
              }
              onPngDownload={() =>
                downloadPng(
                  forecastGraphRef,
                  `forecast_${modelChoice.replace(/\s+/g, "_").toLowerCase()}`,
                  1500,
                  760
                )
              }
              onZoomIn={() => {
                const currentX = forecastGraphRef.current?.layout?.xaxis?.range as
                  | [string, string]
                  | undefined;
                const currentY = forecastGraphRef.current?.layout?.yaxis?.range as
                  | [number, number]
                  | undefined;

                const nextX = zoomDateRange(currentX, combinedDates, 0.7);
                const nextY = zoomNumberRange(currentY, paddedMinY, paddedMaxY, 0.7);

                relayoutRange(forecastGraphRef, {
                  "xaxis.range": [nextX[0], nextX[1]],
                  "yaxis.range": [nextY[0], nextY[1]],
                });
              }}
              onZoomOut={() => {
                const currentX = forecastGraphRef.current?.layout?.xaxis?.range as
                  | [string, string]
                  | undefined;
                const currentY = forecastGraphRef.current?.layout?.yaxis?.range as
                  | [number, number]
                  | undefined;

                const nextX = zoomDateRange(currentX, combinedDates, 1.35);
                const nextY = zoomNumberRange(currentY, paddedMinY, paddedMaxY, 1.35);

                relayoutRange(forecastGraphRef, {
                  "xaxis.range": [nextX[0], nextX[1]],
                  "yaxis.range": [nextY[0], nextY[1]],
                });
              }}
              onReset={() =>
                relayoutRange(forecastGraphRef, {
                  "xaxis.autorange": true,
                  "yaxis.autorange": true,
                })
              }
              onFullscreen={() => openFullscreen(forecastWrapperRef)}
            />
          </div>

          <div className="forecast-plotly-shell" ref={forecastWrapperRef}>
            <div className="forecast-plotly-chart-wrap">
              <Plot
                data={chartData}
                layout={chartLayout as any}
                config={commonPlotConfig}
                onInitialized={(_, graphDiv) => {
                  forecastGraphRef.current = graphDiv;
                }}
                onUpdate={(_, graphDiv) => {
                  forecastGraphRef.current = graphDiv;
                }}
                useResizeHandler
                className="forecast-plotly-chart"
              />
            </div>
          </div>

          <div className="forecast-legend-mini">
            <span className="forecast-legend-item">
              <span className="forecast-legend-swatch historical" />
              Historical
            </span>
            <span className="forecast-legend-item">
              <span className="forecast-legend-swatch forecast" />
              Forecast
            </span>
            <span className="forecast-legend-item">
              <span className="forecast-legend-swatch interval" />
              Confidence Interval
            </span>
          </div>
        </article>

        <article className="dashboard-card forecast-details-card">
          <div className="forecast-card-head">
            <div className="forecast-card-title">
              <p className="forecast-card-kicker">Forecast Details</p>
              <h3>Predicted daily cost table</h3>
              <p className="forecast-card-subline">
                Daily forecast output with interval bounds and trend label
              </p>
            </div>

            <button
              type="button"
              className="card-link-btn"
              disabled={loading || !detailsRows.length}
              onClick={() =>
                exportCsv(
                  `forecast_table_${modelChoice
                    .replace(/\s+/g, "_")
                    .toLowerCase()}_${forecastHorizon}days.csv`,
                  detailsRows.map((row) => ({
                    date: row.date,
                    forecast: row.forecast,
                    lower: row.lower,
                    upper: row.upper,
                  }))
                )
              }
            >
              Export Table
            </button>
          </div>

          <div className="forecast-table-wrap slim">
            <table className="forecast-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Predicted Cost</th>
                  <th>80% Confidence Range</th>
                  <th>Trend</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={4}>Loading forecast details...</td>
                  </tr>
                ) : detailsRows.length ? (
                  detailsRows.map((row) => (
                    <tr key={row.date}>
                      <td>{row.date}</td>
                      <td>{formatCurrencyPrecise(row.forecast)}</td>
                      <td>
                        {formatCurrencyPrecise(row.lower)} -{" "}
                        {formatCurrencyPrecise(row.upper)}
                      </td>
                      <td>
                        <span className={`forecast-trend-chip ${row.trend.className}`}>
                          {row.trend.label}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4}>No forecast rows available.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="dashboard-card forecast-models-card">
          <div className="forecast-card-head">
            <div className="forecast-card-title">
              <p className="forecast-card-kicker">Model Comparison</p>
              <h3>Compare forecasting models</h3>
              <p className="forecast-card-subline">
                Ranked top-to-bottom snapshot of all available models
              </p>
            </div>

            <label className="forecast-comparison-toggle">
              <input
                type="checkbox"
                checked={showModelComparison}
                onChange={(e) => {
                  setShowModelComparison(e.target.checked);

                  if (!e.target.checked) {
                    setComparisonLoading(false);
                  }
                }}
              />
              <span>Run all models and compare</span>
            </label>
          </div>

          {showModelComparison ? (
            <>
              {comparisonLoading ? (
                <div className="forecast-comparison-loading-inline">
                  <strong>Running comparison models...</strong>
                  <p>
                    Prophet, SARIMAX, ETS, Seasonal Naive, and Naive are being
                    prepared for side-by-side comparison.
                  </p>
                </div>
              ) : rankedComparisonRows.length ? (
                <>
                  <div className="forecast-model-grid">
                    {rankedComparisonRows.map((row) => (
                      <div
                        key={row.model}
                        className={`forecast-model-pill ${getModelCardClass(row.model)}`}
                        style={{
                          borderLeft: `6px solid ${getModelColor(row.model)}`,
                        }}
                      >
                        <div className="forecast-model-pill-top">
                          <span className="forecast-model-rank">#{row.rank}</span>
                          <strong>{row.model}</strong>
                        </div>

                        <div className="forecast-model-pill-stats">
                          <span>
                            Avg Daily:{" "}
                            {row.avg_daily_forecast != null
                              ? formatCurrencyPrecise(row.avg_daily_forecast)
                              : "N/A"}
                          </span>
                          <span>
                            Total Forecast:{" "}
                            {row.total_forecast != null
                              ? formatCurrencyPrecise(row.total_forecast)
                              : "N/A"}
                          </span>
                          <span>
                            vs Historical:{" "}
                            {row.vs_historical_pct != null
                              ? formatPercent(row.vs_historical_pct)
                              : "N/A"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="forecast-table-wrap" style={{ marginTop: 18 }}>
                    <table className="forecast-table">
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>Model</th>
                          <th>Avg Daily Forecast</th>
                          <th>Total Forecast</th>
                          <th>vs Historical</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rankedComparisonRows.map((row) => (
                          <tr
                            key={row.model}
                            className="forecast-model-row"
                            style={{
                              boxShadow: `inset 4px 0 0 ${getModelColor(row.model)}`,
                            }}
                          >
                            <td>#{row.rank}</td>
                            <td>{row.model}</td>
                            <td>
                              {row.avg_daily_forecast != null
                                ? formatCurrencyPrecise(row.avg_daily_forecast)
                                : "N/A"}
                            </td>
                            <td>
                              {row.total_forecast != null
                                ? formatCurrencyPrecise(row.total_forecast)
                                : "N/A"}
                            </td>
                            <td>
                              {row.vs_historical_pct != null
                                ? formatPercent(row.vs_historical_pct)
                                : "N/A"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="forecast-empty-state">
                  <div>
                    <strong>No comparison data available</strong>
                    <p>The backend returned no model comparison rows for this horizon.</p>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="forecast-empty-state">
              <div>
                <strong>Model comparison is collapsed</strong>
                <p>
                  Enable the toggle to preview Prophet, SARIMAX, ETS, Seasonal
                  Naive, and Naive outputs side by side.
                </p>
              </div>
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
