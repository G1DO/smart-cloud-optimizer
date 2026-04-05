import "./intro.css";
import GlobeHero from "../components/hero/globehero";
import { Poppins, Prompt, Archivo_Black, Space_Grotesk, IBM_Plex_Sans, Inter } from "next/font/google";

const space = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space",
  weight: ["500", "600", "700"],
});

const ibm = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-ibm",
  weight: ["400", "500", "600", "700"],
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  weight: ["400", "500", "600"],
});

export const poppins = Poppins({
  subsets: ["latin"],
  weight: ["700"],
  variable: "--font-poppins",
  display: "swap",
});

export const prompt = Prompt({
  subsets: ["latin"],
  weight: ["300"],
  variable: "--font-prompt",
  display: "swap",
});

export const archb = Archivo_Black({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-archb",
  display: "swap",
});

export default function Home() {
  return (
    <>
      <section className="hero-full">
        <div className="hero-grid">
          <div className="hero-left">
            <h1 className="hero-title">Data-Driven Decisions. Predictable Spend.</h1>
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

      <section className="feature-section">
        <div className="feature-container">
          <div className="feature-text">
            <h2 className="feature-title ibm-font">Smart Cost Visibility</h2>
            <p className="inter-font">
              Gain real-time transparency into your AWS spending. Track
              service-level usage, identify anomalies, and understand exactly
              where your budget goes.
            </p>
          </div>
          <div className="feature-video">
            <video src="/videos/demo1.mp4" autoPlay loop muted playsInline />
          </div>
        </div>
      </section>

      <section className="feature-section">
        <div className="feature-container reverse">
          <div className="feature-text">
            <h2 className="feature-title">AI Waste Detection</h2>
            <p className="inter-font">
              Detect idle instances, overprovisioned resources, and inefficient
              scaling patterns automatically. Reduce unnecessary costs without
              affecting performance.
            </p>
          </div>
          <div className="feature-video">
            <video src="/videos/demo2.mp4" autoPlay loop muted playsInline />
          </div>
        </div>
      </section>

      <section className="feature-section">
        <div className="feature-container">
          <div className="feature-text">
            <h2 className="feature-title">Forecast & Optimize</h2>
            <p className="inter-font">
              Predict future cloud expenses using intelligent forecasting.
              Receive actionable recommendations that optimize infrastructure
              while maintaining scalability and reliability.
            </p>
          </div>
          <div className="feature-video">
            <video src="/videos/demo3.mp4" autoPlay loop muted playsInline />
          </div>
        </div>
      </section>

      <section className="team-section">
        <h2 className="section-title">Meet The Team</h2>

        <div className="team-grid">
          <div className="team-card">
            <img src="/team/ahmed.jpg" />
            <h3>Ahmed Sameh Mohamed</h3>
          </div>

          <div className="team-card">
            <img src="/team/hazem.jpg" />
            <h3>Hazem Ibrahim Mohamed</h3>
          </div>

          <div className="team-card">
            <img src="/team/ibrahim.jpg" />
            <h3>Ibrahim Mohamed Abdelsadek</h3>
          </div>

          <div className="team-card">
            <img src="/team/john.jpg" />
            <h3>John Ihab Fathy</h3>
          </div>

          <div className="team-card">
            <img src="/team/mahmoud.jpg" />
            <h3>Mahmoud Ahmed Kamel</h3>
          </div>

          <div className="team-card">
            <img src="/team/mariam.jpg" />
            <h3>Mariam Emad Fawzy</h3>
          </div>
        </div>
      </section>

      <section className="contact-section">
        <h2 className="section-title">Contact Us</h2>

        <form className="contact-form">
          <input type="text" placeholder="Your Name" />
          <input type="email" placeholder="Your Email" />
          <textarea placeholder="Your Message" rows={4}></textarea>
          <button type="submit">Send Message</button>
        </form>
      </section>
    </>
  );
}