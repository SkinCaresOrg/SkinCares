import { Link, useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { isAuthenticated } from "@/lib/session";
import { logout } from "@/lib/auth";

const Navigation = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => location.pathname === path;

  const [isLoggedIn, setIsLoggedIn] = useState(
    isAuthenticated()
  );

  useEffect(() => {
    const checkAuth = () => {
      setIsLoggedIn(isAuthenticated());
    };

    window.addEventListener("storage", checkAuth);

    return () => window.removeEventListener("storage", checkAuth);
  }, []);

  return (
    <nav className="sticky top-0 z-50 border-b border-border/50 bg-card/70 backdrop-blur-xl shadow-sm">
      <div className="container flex h-16 items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo.png" alt="SkinCares" className="h-7 w-auto" />
          <span className="logo-font text-xl text-foreground">
            SkinCares
          </span>
        </Link>

        {/* Right side */}
        <div className="flex items-center gap-4">
          {/* Navigation links */}
          {isLoggedIn &&
            [
              { path: "/catalog", label: "Catalog" },
              { path: "/profile", label: "Profile" },
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
                onClick={() => {
                  logout();
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