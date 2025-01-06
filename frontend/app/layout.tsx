import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SnackbarProvider } from "./components/Snackbar/SnackbarContext";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Admin Panel",
  description: "Admin Panel for managing projects and settings",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <SnackbarProvider>
          {children}
        </SnackbarProvider>
      </body>
    </html>
  );
}