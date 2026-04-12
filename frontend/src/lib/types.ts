export type Category = "cleanser" | "moisturizer" | "sunscreen" | "treatment" | "face_mask" | "eye_cream";
export type Reaction = "like" | "dislike" | "irritation";
export type SortValue = "price_asc" | "price_desc";
export type SkinType = "normal" | "dry" | "oily" | "combination" | "sensitive" | "not_sure";
export type Concern = "acne" | "dryness" | "oiliness" | "redness" | "dark_spots" | "fine_lines" | "dullness" | "large_pores" | "maintenance";
export type SensitivityLevel = "very_sensitive" | "somewhat_sensitive" | "rarely_sensitive" | "not_sensitive" | "not_sure";
export type PriceRange = "budget" | "affordable" | "mid_range" | "premium" | "no_preference";
export type RoutineSize = "minimal" | "basic" | "moderate" | "extensive";
export type IngredientExclusion = "fragrance" | "alcohol" | "essential_oils" | "sulfates" | "parabens";

export interface Product {
  product_id: number;
  product_name: string;
  brand: string;
  category: Category;
  price: number;
  image_url: string;
  short_description?: string;
  rating_count?: number;
  wishlist_supported?: boolean;
}

export interface ProductDetail extends Product {
  ingredients: string[];
  ingredient_highlights?: string[];
  concerns_targeted?: Concern[];
  skin_types_supported?: SkinType[];
}

export interface RecommendedProduct extends Product {
  recommendation_score: number;
  explanation: string;
}

export interface DupeProduct extends Product {
  dupe_score: number;
  explanation: string;
}

export interface OnboardingProfile {
  skin_type: SkinType;
  concerns: Concern[];
  sensitivity_level: SensitivityLevel;
  ingredient_exclusions: IngredientExclusion[];
  price_range: PriceRange;
  routine_size: RoutineSize;
  product_interests: Category[];
}

export interface FeedbackRequest {
  user_id: string;
  product_id: number;
  has_tried: boolean;
  reaction?: Reaction;
  reason_tags?: string[];
  free_text?: string;
}

export const CATEGORIES: Category[] = ["cleanser", "moisturizer", "sunscreen", "treatment", "face_mask", "eye_cream"];

export const CATEGORY_LABELS: Record<Category, string> = {
  cleanser: "Cleanser",
  moisturizer: "Moisturizer",
  sunscreen: "Sunscreen",
  treatment: "Treatment",
  face_mask: "Face Mask",
  eye_cream: "Eye Cream",
};

export const REACTION_TAGS: Record<Category, { like: string[]; dislike: string[] }> = {
  moisturizer: {
    like: ["hydrated_well", "absorbed_quickly", "felt_lightweight", "non_irritating", "good_value"],
    dislike: ["too_greasy", "not_moisturizing_enough", "felt_sticky", "broke_me_out", "price_too_high"],
  },
  cleanser: {
    like: ["not_drying", "very_gentle", "helped_oil_control", "good_value", "other"],
    dislike: ["made_skin_dry_tight", "didnt_clean_well", "irritated_skin", "broke_me_out", "price_too_high", "other"],
  },
  face_mask: {
    like: ["skin_felt_smoother", "more_hydrated", "looked_brighter", "helped_oil_acne", "good_value", "other"],
    dislike: ["smelled_bad", "burned_or_stung", "too_drying", "didnt_see_results", "uncomfortable", "price_too_high", "other"],
  },
  treatment: {
    like: ["helped_acne", "helped_dark_spots", "helped_hydration", "helped_texture", "helped_wrinkles", "good_value", "other"],
    dislike: ["irritated_skin", "didnt_work", "too_strong", "broke_me_out", "price_too_high", "other"],
  },
  eye_cream: {
    like: ["improved_dryness", "improved_dark_circles", "improved_puffiness", "improved_fine_lines", "improved_eye_bags", "moisturizing", "good_value", "other"],
    dislike: ["irritated_eyes", "too_heavy", "didnt_work", "caused_bumps", "price_too_high", "other"],
  },
  sunscreen: {
    like: ["non_irritating", "absorbed_well", "felt_lightweight", "no_white_cast", "good_value", "other"],
    dislike: ["left_white_cast", "felt_greasy", "broke_me_out", "irritated_skin", "caused_sunburn", "price_too_high", "other"],
  },
};

export const IRRITATION_TAGS = ["burning", "stinging", "redness", "itching", "rash", "broke_me_out", "other"];

export function formatTagLabel(tag: string): string {
  return tag.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatPrice(price: number): string {
  return `$${price.toFixed(2)}`;
}
