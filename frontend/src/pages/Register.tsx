import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

import { register } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import Navigation from "@/components/Navigation";


export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const navigate = useNavigate();

  const handleRegister = async () => {
    setErrorMsg("");
    try {
      // Frontend pre-checks
      if (!email || !password) {
        setErrorMsg("Please fill in both email and password.");
        return;
      }
      if (password.length < 8) {
        setErrorMsg("Password must be at least 8 characters long.");
        return;
      }

      // Call backend
      await register(email, password);

      // Success → redirect to login
      navigate("/login");
    } catch (error: any) {
      console.error("Registration failed:", error);

      if (error instanceof ApiError) {
        setErrorMsg(error.detail);
      } else {
        setErrorMsg("Registration failed. Please try again.");
      }
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
              Create an account
            </h1>
            <p className="text-sm text-muted-foreground mt-2">
              Start your personalized skincare journey
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

          {/* Error Message */}
          {errorMsg && (
            <p className="text-center text-sm text-red-500">{errorMsg}</p>
          )}

          {/* Button */}
          <button
            onClick={handleRegister}
            className="flex items-center justify-center gap-2 rounded-2xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition-all hover:bg-primary-hover hover:shadow-xl"
          >
            Sign Up <ArrowRight className="h-4 w-4" />
          </button>

          {/* Redirect */}
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <span
              onClick={() => navigate("/login")}
              className="cursor-pointer text-primary hover:underline"
            >
              Log in
            </span>
          </p>
        </motion.div>
      </main>
    </div>
  );
}