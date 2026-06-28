import "./intro.css";
import GlobeHero from "../components/hero/globehero";

export default function Home() {
  return (
    <div className="intro-page">

      <section className="hero-full">
        <div className="hero-grid">
          <div className="hero-left">
            <h1 className="hero-title">
              <span>Data-Driven</span>
              <span>Decisions.</span>
              <span>Predictable Spend.</span>
            </h1>
            <h3 className="hero-gradient">Sustainable Cloud.</h3>

            <p className="hero-sub">
              OptiCloud transforms complex AWS billing data into clear insights,
              automated forecasts, and AI-powered savings recommendations — so your
              infrastructure scales efficiently, not expensively.
            </p>

            <div className="hero-buttons">
              <button className="btn-freetrial">Start Free Trial</button>
              <button className="btn-demo">Watch Demo</button>
            </div>
          </div>

          <div className="hero-right">
            {/* ✅ Cloudflare-like: part of globe comes from outside + clipped */}
            <div className="hero-globe-wrap">
              <GlobeHero />
            </div>
          </div>
        </div>
      </section>

      <section className="ops-section ops-section-first">
        <div className="ops-copy">
          <span className="section-kicker">AWS COST OPERATIONS</span>
          <h2>Turn AWS billing noise into DevOps decisions.</h2>
          <p>
            OptiCloud connects cloud cost signals with engineering context, so
            teams can see spend movement, forecast risk, and act on the highest
            impact optimization opportunities before the invoice grows.
          </p>

          <div className="ops-points">
            <span>Service-level cost visibility</span>
            <span>Anomaly detection for unusual spikes</span>
            <span>AI-assisted recommendation workflow</span>
          </div>
        </div>

        <div className="aws-visual-card" aria-hidden="true">
          <div className="aws-grid" />
          <div className="aws-cloud">AWS</div>
          
          <div className="signal-node node-a" />
          <div className="signal-node node-b" />
          <div className="signal-node node-c" />
          <div className="signal-node node-d" />
          <div className="signal-panel panel-cost">
            <span>Total cost</span>
            <strong>$2.4k</strong>
          </div>
          <div className="signal-panel panel-risk">
            <span>Anomaly risk</span>
            <strong>Low</strong>
          </div>
          <div className="signal-bars">
            <span className="signal-bar bar-sm" />
            <span className="signal-bar bar-md" />
            <span className="signal-bar bar-lg" />
            <span className="signal-bar bar-xl" />
            <span className="signal-bar bar-md" />
          </div>
        </div>
      </section>

      <section className="workflow-section">
        <div className="section-heading">
          <span className="section-kicker">CLOUD FINOPS WORKFLOW</span>
          <h2>From AWS usage to accountable action.</h2>
          <p>
            A clear operational path for teams that need cost governance without
            slowing down delivery.
          </p>
        </div>

        <div className="workflow-grid">
          <article className="workflow-card">
            <span className="workflow-number">01</span>
            <h3>Collect</h3>
            <p>Read AWS cost and usage data across services and accounts.</p>
          </article>

          <article className="workflow-card">
            <span className="workflow-number">02</span>
            <h3>Analyze</h3>
            <p>Detect daily cost trends, spikes, service drivers, and waste patterns.</p>
          </article>

          <article className="workflow-card">
            <span className="workflow-number">03</span>
            <h3>Forecast</h3>
            <p>Predict monthly spend and expose risk before it becomes budget pressure.</p>
          </article>

          <article className="workflow-card">
            <span className="workflow-number">04</span>
            <h3>Optimize</h3>
            <p>Prioritize recommendations by savings impact, service, confidence, and risk.</p>
          </article>
        </div>
      </section>

      <section className="reco-section">
        <div className="reco-board" aria-hidden="true">
          <div className="reco-card high">
            <span>HIGH PRIORITY</span>
            <strong>Right-size EC2 instances</strong>
            <p>Reduce idle compute spend</p>
          </div>
          <div className="reco-card medium">
            <span>MEDIUM PRIORITY</span>
            <strong>Review RDS utilization</strong>
            <p>Match capacity to demand</p>
          </div>
          <div className="reco-card low">
            <span>LOW PRIORITY</span>
            <strong>Clean unused storage</strong>
            <p>Archive cold S3 objects</p>
          </div>
        </div>

        <div className="ops-copy">
          <span className="section-kicker">AI RECOMMENDATIONS</span>
          <h2>Prioritized savings that engineers can trust.</h2>
          <p>
            Recommendations are presented with priority, service context, risk,
            and estimated savings so the team can choose the safest action first.
          </p>

          <div className="metric-strip">
            <div>
              <strong>30-day</strong>
              <span>forecast horizon</span>
            </div>
            <div>
              <strong>Top 3</strong>
              <span>quick wins</span>
            </div>
            <div>
              <strong>AWS</strong>
              <span>focused insights</span>
            </div>
          </div>
        </div>
      </section>

      <section className="team-section redesigned-team">
        <div className="section-heading">
          <span className="section-kicker">GRADUATION PROJECT TEAM</span>
          <h2>Built for practical cloud cost control.</h2>
          <p>
            OptiCloud was developed as a DevOps-focused graduation project that
            combines backend analytics, AI-guided onboarding, AWS cost modeling,
            and a production-style dashboard experience.
          </p>
        </div>

        <div className="team-grid">
          <div className="team-card">
            <span>AS</span>
            <h3>Ahmed Sameh Mohamed</h3>
          </div>

          <div className="team-card">
            <span>HI</span>
            <h3>Hazem Ibrahim Mohamed</h3>
          </div>

          <div className="team-card">
            <span>IM</span>
            <h3>Ibrahim Mohamed Abdelsadek</h3>
          </div>

          <div className="team-card">
            <span>JI</span>
            <h3>John Ihab Fathy</h3>
          </div>

          <div className="team-card">
            <span>MK</span>
            <h3>Mahmoud Ahmed Kamel</h3>
          </div>

          <div className="team-card">
            <span>ME</span>
            <h3>Mariam Emad Fawzy</h3>
          </div>
        </div>
      </section>

      <footer className="site-footer">
        <div className="footer-brand">
          <h2>OptiCloud</h2>
          <p>
            AWS cloud cost optimizer for forecasting, anomaly detection, and
            AI-assisted recommendations.
          </p>
        </div>

        <div className="footer-columns">
          <div>
            <h3>Platform</h3>
            <span>Cost Dashboard</span>
            <span>Forecasts</span>
            <span>Recommendations</span>
            <span>Guided Questions</span>
          </div>

          <div>
            <h3>DevOps Value</h3>
            <span>Reduce waste</span>
            <span>Track anomalies</span>
            <span>Plan budgets</span>
            <span>Act faster</span>
          </div>

          <div>
            <h3>AWS Scope</h3>
            <span>EC2</span>
            <span>RDS</span>
            <span>S3</span>
            <span>Multi-service spend</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
