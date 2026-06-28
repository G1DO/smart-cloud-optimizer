"use client";

import { usePathname } from "next/navigation";
import Navbar from "../components/navbar/navbar";
import SplashScreen from "../components/splash/splashscreen";


export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isDashboardPage = pathname.startsWith("/dashboard");

  return (
    <>
      <div className="background-blobs">
        <span className="blob blob1"></span>
        <span className="blob blob2"></span>
        <span className="blob blob3"></span>
        <span className="blob blob4"></span>
      </div>

      <SplashScreen>
        {!isDashboardPage && <Navbar />}
        <main className="space-font">{children}</main>
      </SplashScreen>
    </>
  );
}