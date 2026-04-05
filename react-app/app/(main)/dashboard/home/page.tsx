"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Plotly from "plotly.js-dist-min";
import type { Layout, Config, Data } from "plotly.js";
import "../home/dashboard.css";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

/* =========================================================
   TYPES
========================================================= */

type KPI = {
  label: string;
  value: string;
  delta?: string;
  trend?: "up" | "down" | "neutral";
  icon: string;
};

type CostPoint = {
  day: string;
  fullDate: string;
  value: number;
};

type ServiceCost = {
  service: string;
  cost: number;
  percent: number;
};

type Recommendation = {
  id: string;
  title: string;
  service: string;
  description: string;
  savings: string;
  priority: "High" | "Medium" | "Low";
  risk: "Low" | "Medium" | "High";
};

type ForecastItem = {
  label: string;
  value: string;
  hint: string;
};

type DashboardHomeApiResponse = {
  summary: {
    total_cost: number;
    potential_savings: number;
    recommendations_count: number;
    anomalies_count: number;
    start_date?: string | null;
    end_date?: string | null;
    days_count?: number;
  };
  daily_costs: {
    date: string;
    total_cost: number;
  }[];
  top_services: {
    service: string;
    total_cost: number;
  }[];
  top_recommendations: {
    id: string;
    title: string;
    service: string;
    description: string;
    savings: number;
    priority: "High" | "Medium" | "Low";
    risk: "Low" | "Medium" | "High";
  }[];
  recent_anomalies: {
    id: string;
    date: string;
    service: string;
    actual_cost: number;
    expected_cost: number;
    severity: "Low" | "Medium" | "High";
    description: string;
  }[];
};

/* =========================================================
   HELPERS
========================================================= */

function formatCurrency(value: number) {
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
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

function formatDateLabel(date: string) {
  const dateObj = new Date(date);
  return dateObj.toLocaleDateString(undefined, {
    month: "short",
    day: "2-digit",
  });
}

function formatAnomalyLine(
  date: string,
  service: string,
  actualCost: number,
  description: string
) {
  return `${formatDateLabel(date)}: ${service} spike detected at ${formatCurrency(
    actualCost
  )} — ${description}`;
}

function normalizePriority(
  value?: string
): "High" | "Medium" | "Low" {
  if (value === "High" || value === "Medium" || value === "Low") return value;
  return "Medium";
}

function normalizeRisk(
  value?: string
): "High" | "Medium" | "Low" {
  if (value === "High" || value === "Medium" || value === "Low") return value;
  return "Medium";
}

/* =========================================================
   TOOLBAR
========================================================= */

function ToolbarButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className="home-chart-tool-btn"
      onClick={onClick}
      title={label}
      aria-label={label}
    >
      {children}
    </button>
  );
}

function ChartToolbar({
  onCsvDownload,
  onDownload,
  onZoomIn,
  onZoomOut,
  onReset,
  onFullscreen,
}: {
  onCsvDownload: () => void;
  onDownload: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onFullscreen: () => void;
}) {
  return (
    <div className="home-chart-tools">
      <ToolbarButton label="Download CSV" onClick={onCsvDownload}>
        <img
          src="/icons/imagebar/download.png"
          alt="download"
          className="bar-icon-img"
        />
      </ToolbarButton>

      <ToolbarButton label="Download plot as PNG" onClick={onDownload}>
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

      <ToolbarButton label="Fullscreen" onClick={onFullscreen}>
        <img
          src="/icons/imagebar/full.png"
          alt="full"
          className="bar-icon-img"
        />
      </ToolbarButton>
    </div>
  );
}

/* =========================================================
   CHART COMPONENT
========================================================= */

function DashboardTrendChart({ data }: { data: CostPoint[] }) {
  const graphRef = useRef<any>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const updateDarkMode = () => {
      const shell =
        wrapperRef.current?.closest(".dashboard-shell") ??
        document.querySelector(".dashboard-shell");

      const darkDetected =
        shell?.classList.contains("dashboard-dark") ||
        document.documentElement.classList.contains("dark") ||
        document.body.classList.contains("dark");

      setIsDark(Boolean(darkDetected));
    };

    updateDarkMode();

    const shell =
      wrapperRef.current?.closest(".dashboard-shell") ??
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

  const xValues = data.map((item) => item.fullDate);
  const yValues = data.map((item) => item.value);

  const paddedStartDate =
    xValues.length > 0
      ? new Date(
        new Date(xValues[0]).getTime() - 12 * 60 * 60 * 1000
      ).toISOString()
      : undefined;

  const paddedEndDate =
    xValues.length > 0
      ? new Date(
        new Date(xValues[xValues.length - 1]).getTime() +
        12 * 60 * 60 * 1000
      ).toISOString()
      : undefined;

  const csvRows = data.map((item) => ({
    day: item.day,
    date: item.fullDate,
    total_cost_usd: item.value,
  }));

  const safeYValues = yValues.length ? yValues : [0];
  const minY = Math.min(...safeYValues);
  const maxY = Math.max(...safeYValues);
  const spread = maxY - minY || 10;

  const paddedMinY = Math.max(
    0,
    minY - Math.max(10, Math.round(spread * 0.18))
  );
  const paddedMaxY = maxY + Math.max(10, Math.round(spread * 0.18));

  const axisColor = isDark ? "#dbeafe" : "#001938";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.22)" : "#00193841";
  const spikeColor = isDark ? "rgba(219, 234, 254, 0.28)" : "#00193841";
  const hoverBg = isDark ? "#0f172a" : "#ffffff";
  const hoverBorder = isDark
    ? "rgba(148, 163, 184, 0.24)"
    : "rgba(15, 52, 107, 0.14)";
  const hoverText = isDark ? "#e2e8f0" : "#4c5d79";

  const downloadPng = async () => {
    if (!graphRef.current) return;
    await Plotly.downloadImage(graphRef.current, {
      format: "png",
      filename: "cloud_spend_trajectory",
      width: 1400,
      height: 700,
    } as any);
  };

  const zoomIn = async () => {
    if (!graphRef.current) return;

    const currentX = graphRef.current.layout?.xaxis?.range as
      | [string, string]
      | undefined;

    const currentY = graphRef.current.layout?.yaxis?.range as
      | [number, number]
      | undefined;

    const nextX = zoomDateRange(currentX, xValues, 0.7);
    const nextY = zoomNumberRange(currentY, paddedMinY, paddedMaxY, 0.7);

    await Plotly.relayout(graphRef.current, {
      "xaxis.range": [nextX[0], nextX[1]],
      "yaxis.range": [nextY[0], nextY[1]],
    } as any);
  };

  const zoomOut = async () => {
    if (!graphRef.current) return;

    const currentX = graphRef.current.layout?.xaxis?.range as
      | [string, string]
      | undefined;

    const currentY = graphRef.current.layout?.yaxis?.range as
      | [number, number]
      | undefined;

    const nextX = zoomDateRange(currentX, xValues, 1.35);
    const nextY = zoomNumberRange(currentY, paddedMinY, paddedMaxY, 1.35);

    await Plotly.relayout(graphRef.current, {
      "xaxis.range": [nextX[0], nextX[1]],
      "yaxis.range": [nextY[0], nextY[1]],
    } as any);
  };

  const resetAxes = async () => {
    if (!graphRef.current) return;

    await Plotly.relayout(graphRef.current, {
      "xaxis.autorange": true,
      "yaxis.autorange": true,
    } as any);
  };

  const openFullscreen = async () => {
    if (!wrapperRef.current) return;

    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }

    await wrapperRef.current.requestFullscreen();
  };

  const plotData: Partial<Data>[] =
    data.length > 0
      ? [
        {
          x: xValues,
          y: yValues,
          type: "scatter",
          mode: "lines+markers",
          name: "",
          line: {
            color: "#2f6fff",
            width: 4,
            shape: "linear",
          },
          marker: {
            size: 10,
            color: "#ffffff",
            line: {
              color: "#2f6fff",
              width: 3,
            },
          },
          fill: "tozeroy",
          fillcolor: "rgba(47, 111, 255, 0.18)",
          hoverlabel: {
            bgcolor: hoverBg,
            bordercolor: hoverBorder,
            font: {
              color: hoverText,
              size: 12,
            },
          },
          hovertemplate:
            "<b>Total daily cost</b><br>" +
            "Date=%{x|%b %-d, %Y}<br>" +
            "Cost (USD)=%{y:.2f}<extra></extra>",
        },
      ]
      : [];

  const plotLayout: Partial<Layout> = {
    autosize: true,
    height: 380,
    margin: { l: 90, r: 24, t: 12, b: 90 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    showlegend: false,
    hovermode: "closest",
    dragmode: "zoom",
    annotations:
      data.length === 0
        ? [
          {
            text: "No cost data available",
            xref: "paper",
            yref: "paper",
            x: 0.5,
            y: 0.5,
            showarrow: false,
            font: {
              size: 16,
              color: axisColor,
            },
          },
        ]
        : [],
    xaxis: {
      title: {
        text: "Date",
        font: {
          size: 14,
          color: axisColor,
        },
      },
      type: "date",
      tickformat: "%b %d",
      range:
        paddedStartDate && paddedEndDate
          ? [paddedStartDate, paddedEndDate]
          : undefined,
      color: axisColor,
      tickfont: {
        size: 12,
        color: axisColor,
      },
      showgrid: false,
      zeroline: false,
      showline: false,
      showspikes: true,
      spikesnap: "data",
      spikecolor: spikeColor,
      spikethickness: 1.4,
      spikedash: "dot",
    },
    yaxis: {
      title: {
        text: "Cost (USD)",
        font: {
          size: 14,
          color: axisColor,
        },
      },
      color: axisColor,
      tickfont: {
        size: 12,
        color: axisColor,
      },
      tickprefix: "$",
      showgrid: true,
      gridcolor: gridColor,
      gridwidth: 1,
      zeroline: false,
      showline: false,
      rangemode: "tozero",
    },
  };

  const plotConfig: Partial<Config> = {
    responsive: true,
    displayModeBar: false,
    displaylogo: false,
    scrollZoom: true,
  };

  return (
    <div className="home-plotly-shell home-plotly-shell-flat" ref={wrapperRef}>
      <div className="chart-top-meta">
        <p className="card-eyebrow">30-Day Trend</p>
        <span className="legend-note">Updated from backend API</span>
      </div>

      <div className="home-plotly-topbar">
        <div className="home-plotly-titles">
          <div className="home-plotly-title-row">
            <h4>Cloud spend trajectory</h4>
          </div>
        </div>

        <ChartToolbar
          onCsvDownload={() => exportCsv("cloud_spend_trajectory.csv", csvRows)}
          onDownload={downloadPng}
          onZoomIn={zoomIn}
          onZoomOut={zoomOut}
          onReset={resetAxes}
          onFullscreen={openFullscreen}
        />
      </div>

      <div className="chart-legend chart-legend-below-title">
        <span className="legend-item">
          <span className="legend-dot primary" />
          Total daily cost
        </span>
      </div>

      <div className="home-plotly-chart-wrap">
        <Plot
          data={plotData}
          layout={plotLayout as any}
          config={plotConfig}
          onInitialized={(_, graphDiv) => {
            graphRef.current = graphDiv;
          }}
          onUpdate={(_, graphDiv) => {
            graphRef.current = graphDiv;
          }}
          useResizeHandler
          className="home-plotly-chart"
        />
      </div>
    </div>
  );
}

/* =========================================================
   MAIN PAGE
========================================================= */

export default function DashboardPage() {
  const [dashboardData, setDashboardData] =
    useState<DashboardHomeApiResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [userId, setUserId] = useState("aws-SYNTHETIC-001");
  const [displayName, setDisplayName] = useState("Cloud User");

  useEffect(() => {
    const storedUserId =
      typeof window !== "undefined"
        ? localStorage.getItem("auth_user_id")
        : null;

    const storedDisplayName =
      typeof window !== "undefined"
        ? localStorage.getItem("auth_display_name")
        : null;

    const resolvedUserId = storedUserId || "aws-SYNTHETIC-001";
    const resolvedDisplayName = storedDisplayName || "Cloud User";

    setUserId(resolvedUserId);
    setDisplayName(resolvedDisplayName);

    async function loadDashboardData() {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(
          `http://127.0.0.1:8000/api/dashboard/home?user_id=${encodeURIComponent(
            resolvedUserId
          )}`
        );

        if (!response.ok) {
          throw new Error("Failed to load dashboard data");
        }

        const result: DashboardHomeApiResponse = await response.json();
        setDashboardData(result);
      } catch (err) {
        console.error("Dashboard API error:", err);
        setError("Could not load live dashboard data.");
      } finally {
        setLoading(false);
      }
    }

    loadDashboardData();
  }, []);

  const costTrend: CostPoint[] = useMemo(() => {
    if (!dashboardData?.daily_costs) return [];

    return dashboardData.daily_costs.map((item) => {
      const dateObj = new Date(item.date);

      return {
        day: String(dateObj.getDate()).padStart(2, "0"),
        fullDate: item.date,
        value: item.total_cost,
      };
    });
  }, [dashboardData]);

  const topServices: ServiceCost[] = useMemo(() => {
    if (!dashboardData?.top_services?.length) return [];

    const totalServicesCost = dashboardData.top_services.reduce(
      (sum, item) => sum + item.total_cost,
      0
    );

    return dashboardData.top_services.map((item) => ({
      service: item.service,
      cost: item.total_cost,
      percent:
        totalServicesCost > 0
          ? Number(((item.total_cost / totalServicesCost) * 100).toFixed(1))
          : 0,
    }));
  }, [dashboardData]);

  const recommendations: Recommendation[] = useMemo(() => {
    if (!dashboardData?.top_recommendations?.length) return [];

    return dashboardData.top_recommendations.map((item) => ({
      id: item.id,
      title: item.title,
      service: item.service,
      description: item.description,
      savings: `${formatCurrency(item.savings)}/mo`,
      priority: normalizePriority(item.priority),
      risk: normalizeRisk(item.risk),
    }));
  }, [dashboardData]);

  const anomalies = useMemo(() => {
    if (!dashboardData?.recent_anomalies?.length) return [];

    return dashboardData.recent_anomalies.map((item) =>
      formatAnomalyLine(
        item.date,
        item.service,
        item.actual_cost,
        item.description
      )
    );
  }, [dashboardData]);

  const forecasts: ForecastItem[] = [
    {
      label: "7-Day Forecast",
      value: "$3,040",
      hint: "Forecast endpoint will be connected next",
    },
    {
      label: "30-Day Forecast",
      value: "$13,190",
      hint: "Using mock value temporarily",
    },
    {
      label: "Confidence Range",
      value: "$12.6k - $13.8k",
      hint: "Will be loaded from forecasts API",
    },
  ];

  const kpis: KPI[] = [
    {
      label: "Total Cloud Cost",
      value: formatCurrency(dashboardData?.summary?.total_cost ?? 0),
      delta: "Last 30 days",
      trend: "neutral",
      icon: "/icons/dashboard/money.png",
    },
    {
      label: "Potential Savings",
      value: `${formatCurrency(
        dashboardData?.summary?.potential_savings ?? 0
      )}/mo`,
      delta: `${dashboardData?.summary?.recommendations_count ?? 0} recommendations`,
      trend: "down",
      icon: "/icons/dashboard/saving.png",
    },
    {
      label: "Forecasted Next Month",
      value: "$13,190",
      delta: "Forecast API next",
      trend: "up",
      icon: "/icons/dashboard/diagram.png",
    },
    {
      label: "Anomalies Detected",
      value: String(dashboardData?.summary?.anomalies_count ?? 0),
      delta: "Last 30 days",
      trend: "neutral",
      icon: "/icons/dashboard/error.png",
    },
  ];

  const getPriorityClass = (priority: Recommendation["priority"]) => {
    if (priority === "High") return "priority-high";
    if (priority === "Medium") return "priority-medium";
    return "priority-low";
  };

  const getPriorityAccentClass = (priority: Recommendation["priority"]) => {
    if (priority === "High")
      return "recommendation-accent recommendation-accent-high";
    if (priority === "Medium")
      return "recommendation-accent recommendation-accent-medium";
    return "recommendation-accent recommendation-accent-low";
  };

  const getTrendClass = (trend?: KPI["trend"]) => {
    if (trend === "up") return "metric-delta up";
    if (trend === "down") return "metric-delta down";
    return "metric-delta neutral";
  };

  const getRiskClass = (risk: Recommendation["risk"]) => {
    if (risk === "High") return "recommendation-tag risk-tag-high";
    if (risk === "Medium") return "recommendation-tag risk-tag-medium";
    return "recommendation-tag risk-tag-low";
  };

  return (
    <>
      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <span className="hero-badge">
            <span className="hero-badge-star">✦</span>
            Live Account Monitoring
          </span>

          <h1>Control AWS spend with clarity,</h1>
          <h3 className="hero-gradient">forecast risk before it grows.</h3>

          <p>
            Track spend behavior, detect anomalies, and surface the highest
            impact savings opportunities across your cloud environment from one
            unified dashboard.
          </p>

          <div className="hero-actions">
            <button type="button" className="hero-primary-btn">
              View Full Cost Analysis
            </button>

            <button type="button" className="hero-secondary-btn">
              Export Executive Snapshot
            </button>
          </div>
        </div>

        <div className="dashboard-hero-side">
          <div className="dashboard-hero-panel">
            <div className="hero-side-mini-card">
              <div className="hero-panel-card">
                <div className="hero-panel-top">
                  <p>Connected Account</p>
                  <span className="status-pill">
                    <span className="status-dot" />
                    Healthy
                  </span>
                </div>

                <h3>{userId}</h3>

                <div className="hero-panel-grid">
                  <div>
                    <span>Owner</span>
                    <strong>{displayName}</strong>
                  </div>

                  <div>
                    <span>Region Scope</span>
                    <strong>Multi-region</strong>
                  </div>

                  <div>
                    <span>Optimization State</span>
                    <strong>Active</strong>
                  </div>

                  <div>
                    <span>Forecast Model</span>
                    <strong>Prophet</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {loading && (
        <section className="dashboard-card" style={{ marginBottom: "24px" }}>
          <div className="card-header">
            <div>
              <p className="card-eyebrow">Loading</p>
              <h3>Fetching live dashboard data...</h3>
            </div>
          </div>
        </section>
      )}

      {error && (
        <section className="dashboard-card" style={{ marginBottom: "24px" }}>
          <div className="card-header">
            <div>
              <p className="card-eyebrow">API Error</p>
              <h3>{error}</h3>
            </div>
          </div>
        </section>
      )}

      <section className="metrics-grid">
        {kpis.map((metric, index) => (
          <article
            key={metric.label}
            className={`metric-card metric-tone-${index + 1}`}
          >
            <div className="metric-card-top">
              <span>{metric.label}</span>

              <div className={`metric-card-icon metric-card-icon-${index + 1}`}>
                <img
                  src={metric.icon}
                  alt={metric.label}
                  className="metric-card-logo"
                />
              </div>
            </div>

            <h3>{metric.value}</h3>
            {metric.delta && (
              <p className={getTrendClass(metric.trend)}>{metric.delta}</p>
            )}
            <div className={`metric-bottom-line metric-line-${index + 1}`} />
          </article>
        ))}
      </section>

      <section className="dashboard-main-grid">
        <article className="dashboard-card chart-card">
          <DashboardTrendChart data={costTrend} />
        </article>

        <article className="dashboard-card side-card">
          <div className="card-header compact">
            <div>
              <p className="card-eyebrow">Forecast Engine</p>
              <h3>Prediction snapshot</h3>
            </div>
          </div>

          <div className="forecast-stack">
            {forecasts.map((item) => (
              <div className="forecast-mini-card" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <p>{item.hint}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="dashboard-bottom-grid">
        <article className="dashboard-card top-contributors-card">
          <div className="card-header">
            <div>
              <p className="card-eyebrow">Service Breakdown</p>
              <h3>Top cost contributors</h3>
            </div>
          </div>

          <div className="services-list">
            {topServices.map((service, index) => (
              <div className="service-row" key={service.service}>
                <div className="service-row-left">
                  <div className={`service-icon service-icon-${(index % 5) + 1}`} />
                  <div className="service-copy">
                    <h4>{service.service}</h4>
                    <p>{formatCurrency(service.cost)}</p>
                  </div>
                </div>

                <div className="service-row-right">
                  <div className="service-bar">
                    <div
                      className={`service-bar-fill service-fill-${(index % 5) + 1}`}
                      style={{ width: `${service.percent}%` }}
                    />
                  </div>
                  <span>{service.percent}%</span>
                </div>
              </div>
            ))}

            {!topServices.length && !loading && (
              <div className="service-row">
                <div className="service-row-left">
                  <div className="service-copy">
                    <h4>No service data available</h4>
                    <p>The backend did not return service breakdown yet.</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </article>

        <article className="dashboard-card">
          <div className="card-header">
            <div>
              <p className="card-eyebrow">Optimizer Output</p>
              <h3>Top recommendations</h3>
            </div>

            <button className="card-link-btn" type="button">
              View all
            </button>
          </div>

          <div className="recommendations-stack">
            {recommendations.map((rec) => (
              <div className="recommendation-card" key={rec.id}>
                <div className={getPriorityAccentClass(rec.priority)} />
                <div className="recommendation-top">
                  <div className="recommendation-main">
                    <div>
                      <h4>{rec.title}</h4>
                      <p>{rec.description}</p>
                    </div>
                  </div>

                  <span className={`priority-pill ${getPriorityClass(rec.priority)}`}>
                    {rec.priority}
                  </span>
                </div>

                <div className="recommendation-meta">
                  <span className="recommendation-tag service-tag">
                    {rec.service}
                  </span>
                  <span className={getRiskClass(rec.risk)}>
                    {rec.risk} Risk
                  </span>
                  <strong>{rec.savings}</strong>
                </div>
              </div>
            ))}

            {!recommendations.length && !loading && (
              <div className="recommendation-card">
                <div className="recommendation-top">
                  <div className="recommendation-main">
                    <div>
                      <h4>No recommendations available</h4>
                      <p>The backend did not return optimization recommendations yet.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </article>
      </section>

      <section className="dashboard-last-grid">
        <article className="dashboard-card">
          <div className="card-header">
            <div>
              <p className="card-eyebrow">Alerts</p>
              <h3>Recent anomalies</h3>
            </div>
          </div>

          <div className="anomaly-list">
            {anomalies.map((item) => (
              <div className="anomaly-item" key={item}>
                <span className="anomaly-icon">!</span>
                <p>{item}</p>
              </div>
            ))}

            {!anomalies.length && !loading && (
              <div className="anomaly-item">
                <span className="anomaly-icon">!</span>
                <p>No anomalies detected in the last 30 days.</p>
              </div>
            )}
          </div>
        </article>

        <article className="dashboard-card quick-actions-card">
          <div className="card-header">
            <div>
              <p className="card-eyebrow">Quick Actions</p>
              <h3>Next best actions</h3>
            </div>
          </div>

          <div className="quick-actions">
            <button type="button">Run optimizer now</button>
            <button type="button">Generate 30-day forecast</button>
            <button type="button">Open recommendations report</button>
            <button type="button">Manage AWS connections</button>
          </div>
        </article>
      </section>
    </>
  );
}