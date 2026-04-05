"use client";

import { useEffect, useState } from "react";
import "./splash.css";
import Image from "next/image";

export default function SplashScreen({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false);
    }, 3000); // 3 seconds

    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div className="splash-container">
        <div className="background-blobs">
        <span className="blob blob1"></span>
        <span className="blob blob2"></span>
        <span className="blob blob3"></span>
        <span className="blob blob4"></span>
      
        </div>
        <div className="splash-content">
            <Image
              src="/icons/logo.png"
              alt="Logo"
              width={500}
              height={400}
              className="logo-zoom"
            />
            <h1 className="splash-title coiny-font">OptiCloud</h1>
            <div className="loader-line"></div>
          </div>
      </div>
    );
  }

  return <>{children}</>;
}