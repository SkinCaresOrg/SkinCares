import { useNavigate } from "react-router-dom";
import { Sparkles, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

import Navigation from "@/components/Navigation";

const Index = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <main className="container flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center px-4 py-20 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex max-w-lg flex-col items-center gap-6"
        >
          <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-primary/10">
            <Sparkles className="h-10 w-10 text-primary" />
          </div>

          <h1 className="font-display text-4xl font-bold leading-tight text-foreground sm:text-5xl">
            Your skin, <span className="text-primary">understood</span>
          </h1>

          <p className="max-w-sm text-base leading-relaxed text-muted-foreground">
            Get personalized skincare recommendations powered by your unique skin profile. No guesswork, just results.
          </p>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              onClick={() => navigate("/login")}
              className="flex items-center gap-2 rounded-2xl bg-primary px-8 py-4 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition-all hover:bg-primary-hover hover:shadow-xl"
            >
              Login <ArrowRight className="h-4 w-4" />
            </button>

            <button
              onClick={() => navigate("/register")}
              className="flex items-center gap-2 rounded-2xl border border-border bg-card px-8 py-4 text-sm font-semibold text-foreground transition-all hover:bg-muted"
            >
              Sign Up <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </motion.div>
      </main>
    </div>
  );
};

export default Index;