import { Link, useLocation } from "react-router-dom";
import { Sparkles, Search } from "lucide-react";

const Navigation = () => {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur-lg">
      <div className="container flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <span className="font-display text-xl font-bold text-foreground">SkinCares</span>
        </Link>
        <div className="flex items-center gap-1">
          {[
            { path: "/catalog", label: "Catalog" },
            { path: "/recommendations", label: "For You" },
            { path: "/swiping", label: "Swiping" },
          ].map(({ path, label }) => (
            <Link
              key={path}
              to={path}
              className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
                isActive(path)
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
};

export default Navigation;
