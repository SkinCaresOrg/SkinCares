import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

import { login } from "@/lib/auth";

// ⚠️ import your Navigation (adjust path if needed)
import Navigation from "@/components/Navigation";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  const handleLogin = async () => {
    try {
      const data = await login(email, password);
      localStorage.setItem("token", data.access_token);
      window.dispatchEvent(new Event("storage"));
      navigate("/catalog");
    } catch (error) {
      console.error("Login failed:", error);
      alert("Login failed. Please check your credentials.");
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <main className="container flex min-h-[calc(100vh-4rem)] items-center justify-center px-4 py-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md flex flex-col gap-6"
        >
          {/* Title */}
          <div className="text-center">
            <h1 className="font-display text-3xl font-bold text-foreground">
              Welcome back
            </h1>
            <p className="text-sm text-muted-foreground mt-2">
              Log in to continue your skincare journey
            </p>
          </div>

          {/* Inputs */}
          <div className="flex flex-col gap-4">
            <input
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-2xl border border-border bg-card px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />

            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-2xl border border-border bg-card px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          {/* Button */}
          <button
            onClick={handleLogin}
            className="flex items-center justify-center gap-2 rounded-2xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition-all hover:bg-primary-hover hover:shadow-xl"
          >
            Login <ArrowRight className="h-4 w-4" />
          </button>

          {/* Redirect */}
          <p className="text-center text-sm text-muted-foreground">
            Don’t have an account?{" "}
            <span
              onClick={() => navigate("/register")}
              className="cursor-pointer text-primary hover:underline"
            >
              Sign up
            </span>
          </p>
        </motion.div>
      </main>
    </div>
  );
}