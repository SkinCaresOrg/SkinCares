import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { submitOnboarding } from "@/lib/api";
import { setUserId } from "@/lib/wishlist";
import { OnboardingProfile, SkinType, SensitivityLevel, PriceRange, RoutineSize, Category, CATEGORIES, CATEGORY_LABELS } from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, Sparkles } from "lucide-react";

const SKIN_TYPES: { value: SkinType; label: string; emoji: string }[] = [
  { value: "normal", label: "Normal", emoji: "✨" },
  { value: "dry", label: "Dry", emoji: "🏜️" },
  { value: "oily", label: "Oily", emoji: "💧" },
  { value: "combination", label: "Combination", emoji: "🔄" },
  { value: "sensitive", label: "Sensitive", emoji: "🌸" },
  { value: "not_sure", label: "Not Sure", emoji: "🤔" },
];

const CONCERNS = [
  { value: "acne", label: "Acne" },
  { value: "dryness", label: "Dryness" },
  { value: "oiliness", label: "Oiliness" },
  { value: "redness", label: "Redness" },
  { value: "dark_spots", label: "Dark Spots" },
  { value: "fine_lines", label: "Fine Lines" },
  { value: "dullness", label: "Dullness" },
  { value: "large_pores", label: "Large Pores" },
  { value: "maintenance", label: "Maintenance" },
];

const SENSITIVITY_LEVELS: { value: SensitivityLevel; label: string }[] = [
  { value: "very_sensitive", label: "Very Sensitive" },
  { value: "somewhat_sensitive", label: "Somewhat Sensitive" },
  { value: "rarely_sensitive", label: "Rarely Sensitive" },
  { value: "not_sensitive", label: "Not Sensitive" },
  { value: "not_sure", label: "Not Sure" },
];

const EXCLUSIONS = [
  { value: "fragrance", label: "Fragrance" },
  { value: "alcohol", label: "Alcohol" },
  { value: "essential_oils", label: "Essential Oils" },
  { value: "sulfates", label: "Sulfates" },
  { value: "parabens", label: "Parabens" },
];

const PRICE_RANGES: { value: PriceRange; label: string; desc: string }[] = [
  { value: "budget", label: "Budget", desc: "Under $15" },
  { value: "affordable", label: "Affordable", desc: "$15–$30" },
  { value: "mid_range", label: "Mid-Range", desc: "$30–$60" },
  { value: "premium", label: "Premium", desc: "$60+" },
  { value: "no_preference", label: "No Preference", desc: "Any price" },
];

const ROUTINE_SIZES: { value: RoutineSize; label: string; desc: string }[] = [
  { value: "minimal", label: "Minimal", desc: "1–2 products" },
  { value: "basic", label: "Basic", desc: "3–4 products" },
  { value: "moderate", label: "Moderate", desc: "5–6 products" },
  { value: "extensive", label: "Extensive", desc: "7+ products" },
];

const TOTAL_STEPS = 7;

const OnboardingForm = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [profile, setProfile] = useState<OnboardingProfile>({
    skin_type: "normal",
    concerns: [],
    sensitivity_level: "not_sure",
    ingredient_exclusions: [],
    price_range: "no_preference",
    routine_size: "basic",
    product_interests: [],
  });

  const updateProfile = <K extends keyof OnboardingProfile>(key: K, val: OnboardingProfile[K]) => {
    setProfile((p) => ({ ...p, [key]: val }));
  };

  const toggleArray = (key: "concerns" | "ingredient_exclusions" | "product_interests", val: string, max?: number) => {
    const arr = profile[key] as string[];
    if (arr.includes(val)) {
      updateProfile(key, arr.filter((v) => v !== val) as any);
    } else if (!max || arr.length < max) {
      updateProfile(key, [...arr, val] as any);
    }
  };

  const canNext = () => {
    if (step === 1) return profile.concerns.length > 0;
    if (step === 6) return profile.product_interests.length > 0;
    return true;
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    const res = await submitOnboarding(profile);
    setUserId(res.user_id);
    navigate("/recommendations");
  };

  const isLast = step === TOTAL_STEPS - 1;

  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-bold text-foreground">What's your skin type?</h2>
            <p className="text-sm text-muted-foreground">This helps us find products that work for your skin.</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {SKIN_TYPES.map((st) => (
                <button
                  key={st.value}
                  onClick={() => updateProfile("skin_type", st.value)}
                  className={`flex flex-col items-center gap-2 rounded-2xl border-2 p-5 transition-all ${
                    profile.skin_type === st.value
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border bg-card hover:border-primary/30"
                  }`}
                >
                  <span className="text-2xl">{st.emoji}</span>
                  <span className="text-sm font-medium text-foreground">{st.label}</span>
                </button>
              ))}
            </div>
          </div>
        );

      case 1:
        return (
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-bold text-foreground">Top skin concerns?</h2>
            <p className="text-sm text-muted-foreground">Select up to 3 concerns you'd like to address.</p>
            <div className="flex flex-wrap gap-2">
              {CONCERNS.map((c) => (
                <button
                  key={c.value}
                  onClick={() => toggleArray("concerns", c.value, 3)}
                  className={`rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                    profile.concerns.includes(c.value)
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "border border-border bg-card text-foreground hover:bg-muted"
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">{profile.concerns.length}/3 selected</p>
          </div>
        );

      case 2:
        return (
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-bold text-foreground">How sensitive is your skin?</h2>
            <p className="text-sm text-muted-foreground">We'll avoid harsh ingredients for sensitive skin.</p>
            <div className="flex flex-col gap-2">
              {SENSITIVITY_LEVELS.map((sl) => (
                <button
                  key={sl.value}
                  onClick={() => updateProfile("sensitivity_level", sl.value)}
                  className={`rounded-2xl border-2 px-5 py-4 text-left text-sm font-medium transition-all ${
                    profile.sensitivity_level === sl.value
                      ? "border-primary bg-primary/5"
                      : "border-border bg-card hover:border-primary/30"
                  }`}
                >
                  {sl.label}
                </button>
              ))}
            </div>
          </div>
        );

      case 3:
        return (
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-bold text-foreground">Any ingredients to avoid?</h2>
            <p className="text-sm text-muted-foreground">Select any ingredients you prefer to exclude.</p>
            <div className="flex flex-wrap gap-2">
              {EXCLUSIONS.map((ex) => (
                <button
                  key={ex.value}
                  onClick={() => toggleArray("ingredient_exclusions", ex.value)}
                  className={`rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                    profile.ingredient_exclusions.includes(ex.value)
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "border border-border bg-card text-foreground hover:bg-muted"
                  }`}
                >
                  {ex.label}
                </button>
              ))}
            </div>
          </div>
        );

      case 4:
        return (
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-bold text-foreground">What's your price range?</h2>
            <p className="text-sm text-muted-foreground">We'll recommend products within your budget.</p>
            <div className="flex flex-col gap-2">
              {PRICE_RANGES.map((pr) => (
                <button
                  key={pr.value}
                  onClick={() => updateProfile("price_range", pr.value)}
                  className={`flex items-center justify-between rounded-2xl border-2 px-5 py-4 transition-all ${
                    profile.price_range === pr.value
                      ? "border-primary bg-primary/5"
                      : "border-border bg-card hover:border-primary/30"
                  }`}
                >
                  <span className="text-sm font-medium text-foreground">{pr.label}</span>
                  <span className="text-xs text-muted-foreground">{pr.desc}</span>
                </button>
              ))}
            </div>
          </div>
        );

      case 5:
        return (
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-bold text-foreground">Ideal routine size?</h2>
            <p className="text-sm text-muted-foreground">How many products do you want in your routine?</p>
            <div className="grid grid-cols-2 gap-3">
              {ROUTINE_SIZES.map((rs) => (
                <button
                  key={rs.value}
                  onClick={() => updateProfile("routine_size", rs.value)}
                  className={`flex flex-col items-center gap-1 rounded-2xl border-2 p-5 transition-all ${
                    profile.routine_size === rs.value
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border bg-card hover:border-primary/30"
                  }`}
                >
                  <span className="text-sm font-medium text-foreground">{rs.label}</span>
                  <span className="text-xs text-muted-foreground">{rs.desc}</span>
                </button>
              ))}
            </div>
          </div>
        );

      case 6:
        return (
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-bold text-foreground">What products interest you?</h2>
            <p className="text-sm text-muted-foreground">Select up to 3 product types.</p>
            <div className="grid grid-cols-2 gap-3">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  onClick={() => toggleArray("product_interests", cat, 3)}
                  className={`rounded-2xl border-2 px-4 py-4 text-sm font-medium transition-all ${
                    profile.product_interests.includes(cat)
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border bg-card hover:border-primary/30"
                  }`}
                >
                  {CATEGORY_LABELS[cat]}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">{profile.product_interests.length}/3 selected</p>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        {/* Progress */}
        <div className="mb-8 flex items-center gap-3">
          <div className="flex-1">
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <motion.div
                className="h-full rounded-full bg-primary"
                initial={{ width: 0 }}
                animate={{ width: `${((step + 1) / TOTAL_STEPS) * 100}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>
          <span className="text-xs font-medium text-muted-foreground">{step + 1}/{TOTAL_STEPS}</span>
        </div>

        {/* Step content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
          >
            {renderStep()}
          </motion.div>
        </AnimatePresence>

        {/* Navigation */}
        <div className="mt-8 flex items-center justify-between gap-4">
          <button
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
            className="flex items-center gap-1 rounded-xl px-4 py-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground disabled:invisible"
          >
            <ChevronLeft className="h-4 w-4" /> Back
          </button>

          {isLast ? (
            <button
              onClick={handleSubmit}
              disabled={!canNext() || submitting}
              className="flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" />
              {submitting ? "Getting ready..." : "Get Recommendations"}
            </button>
          ) : (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={!canNext()}
              className="flex items-center gap-1 rounded-xl bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover disabled:opacity-50"
            >
              Next <ChevronRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default OnboardingForm;
