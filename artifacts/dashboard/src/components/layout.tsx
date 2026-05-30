import { Link, useLocation } from "wouter";
import { Activity } from "lucide-react";

export default function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();

  return (
    <div className="min-h-screen bg-background text-foreground font-sans selection:bg-primary/30">
      <header className="border-b border-border sticky top-0 z-50 bg-background/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-8 h-8 rounded bg-primary text-primary-foreground flex items-center justify-center font-mono font-bold text-xs group-hover:scale-105 transition-transform">
              B&gt;_
            </div>
            <span className="font-semibold tracking-tight">Bera AI API</span>
            <span className="hidden sm:flex items-center gap-1 ml-1 text-xs text-green-400">
              <Activity className="w-3 h-3" /> Live
            </span>
          </Link>
          <nav className="flex items-center gap-6">
            <Link href="/" className={`text-sm font-medium transition-colors hover:text-primary ${location === "/" ? "text-primary" : "text-muted-foreground"}`}>
              Docs
            </Link>
            <Link href="/dashboard" className={`text-sm font-medium transition-colors hover:text-primary ${location === "/dashboard" ? "text-primary" : "text-muted-foreground"}`}>
              Console
            </Link>
            <Link href="/admin" className={`text-sm font-medium transition-colors hover:text-primary ${location === "/admin" ? "text-primary" : "text-muted-foreground"}`}>
              Admin
            </Link>
          </nav>
        </div>
      </header>
      <main className="container mx-auto px-4 py-8">
        {children}
      </main>
      <footer className="border-t border-border py-6 mt-12">
        <div className="container mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>Built by <a href="https://github.com/bera-tech-ai" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Bera Tech</a></span>
          <div className="flex items-center gap-4">
            <a href="/api/docs" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">API Docs</a>
            <a href="https://github.com/bera-tech-ai/cloud-bera" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">GitHub</a>
            <a href="/api/healthz" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">Status</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
