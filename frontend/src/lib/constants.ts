import { SkinType, SensitivityLevel, PriceRange, RoutineSize } from "./types";

export const SKIN_TYPES: { value: SkinType; label: string; emoji: string }[] = [
  { value: "normal", label: "Normal", emoji: "✨" },
  { value: "dry", label: "Dry", emoji: "🏜️" },
  { value: "oily", label: "Oily", emoji: "💧" },
  { value: "combination", label: "Combination", emoji: "🔄" },
  { value: "sensitive", label: "Sensitive", emoji: "🌸" },
  { value: "not_sure", label: "Not Sure", emoji: "🤔" },
];

export const CONCERNS = [
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

export const SENSITIVITY_LEVELS: { value: SensitivityLevel; label: string }[] = [
  { value: "very_sensitive", label: "Very Sensitive" },
  { value: "somewhat_sensitive", label: "Somewhat Sensitive" },
  { value: "rarely_sensitive", label: "Rarely Sensitive" },
  { value: "not_sensitive", label: "Not Sensitive" },
  { value: "not_sure", label: "Not Sure" },
];

export const EXCLUSIONS = [
  { value: "fragrance", label: "Fragrance" },
  { value: "alcohol", label: "Alcohol" },
  { value: "essential_oils", label: "Essential Oils" },
  { value: "sulfates", label: "Sulfates" },
  { value: "parabens", label: "Parabens" },
];

export const PRICE_RANGES: { value: PriceRange; label: string; desc: string }[] = [
  { value: "budget", label: "Budget", desc: "Under $15" },
  { value: "affordable", label: "Affordable", desc: "$15–$30" },
  { value: "mid_range", label: "Mid-Range", desc: "$30–$60" },
  { value: "premium", label: "Premium", desc: "$60+" },
  { value: "no_preference", label: "No Preference", desc: "Any price" },
];

export const ROUTINE_SIZES: { value: RoutineSize; label: string; desc: string }[] = [
  { value: "minimal", label: "Minimal", desc: "1–2 products" },
  { value: "basic", label: "Basic", desc: "3–4 products" },
  { value: "moderate", label: "Moderate", desc: "5–6 products" },
  { value: "extensive", label: "Extensive", desc: "7+ products" },
];
