import { Link, useLocation, useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { useState, useEffect } from "react";

const Navigation = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => location.pathname === path;

  const [isLoggedIn, setIsLoggedIn] = useState(
    !!localStorage.getItem("token")
  );

  useEffect(() => {
    const checkAuth = () => {
      setIsLoggedIn(!!localStorage.getItem("token"));
    };

    window.addEventListener("storage", checkAuth);

    return () => window.removeEventListener("storage", checkAuth);
  }, []);

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur-lg">
      <div className="container flex h-16 items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <span className="font-display text-xl font-bold text-foreground">
            SkinCares
          </span>
        </Link>

        {/* Right side */}
        <div className="flex items-center gap-4">
          {/* Navigation links */}
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

          {/* Auth buttons */}
          {!isLoggedIn ? (
            <>
              <button
                onClick={() => navigate("/register")}
                className="rounded-2xl border border-border bg-card px-4 py-2 text-sm font-semibold text-foreground transition hover:bg-muted"
              >
                Sign Up
              </button>

              <button
                onClick={() => navigate("/login")}
                className="rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow hover:bg-primary-hover transition"
              >
                Login
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => navigate("/profile")}
                className="text-foreground hover:text-primary"
              >
                👤
              </button>

              <button
                onClick={() => {
                  localStorage.removeItem("token");
                  setIsLoggedIn(false);
                  navigate("/");
                }}
                className="rounded-2xl border border-border bg-card px-4 py-2 text-sm font-semibold text-foreground transition hover:bg-muted"
              >
                Logout
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navigation;