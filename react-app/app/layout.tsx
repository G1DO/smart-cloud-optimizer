import type { ReactNode } from "react";
import {
  Poppins,
  Prompt,
  Tilt_Warp,
  Space_Grotesk,
  IBM_Plex_Sans,
  Inter,
  Archivo,
} from "next/font/google";

import "./globals.css";

const space = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space",
  weight: ["500", "600", "700"],
});

const arc = Archivo({
  subsets: ["latin"],
  variable: "--font-arc",
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

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["700"],
  variable: "--font-poppins",
  display: "swap",
});

const prompt = Prompt({
  subsets: ["latin"],
  weight: ["300"],
  variable: "--font-prompt",
  display: "swap",
});

const tiltWarp = Tilt_Warp({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-tilt",
  display: "swap",
});

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${space.variable} ${arc.variable} ${ibm.variable} ${inter.variable} ${poppins.variable} ${prompt.variable} ${tiltWarp.variable}`}
      >
        {children}
      </body>
    </html>
  );
}