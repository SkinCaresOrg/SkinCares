import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { 
  User, 
  Heart, 
  Settings, 
  ChevronRight, 
  Save, 
  CheckCircle2, 
  AlertCircle,
  Loader2
} from "lucide-react";
import Navigation from "@/components/Navigation";
import { getUserProfile, getWishlist } from "@/lib/wishlist";
import { getProductDetail, submitOnboarding } from "@/lib/api";
import { saveOnboardingForCurrentUser } from "@/lib/session";
import { 
  OnboardingProfile, 
  Product, 
  CATEGORIES, 
  CATEGORY_LABELS,
  Category,
  SkinType,
  Concern,
  SensitivityLevel,
  IngredientExclusion,
  PriceRange,
  RoutineSize
} from "@/lib/types";
import { 
  SKIN_TYPES, 
  CONCERNS, 
  SENSITIVITY_LEVELS, 
  EXCLUSIONS, 
  PRICE_RANGES, 
  ROUTINE_SIZES 
} from "@/lib/constants";
import ProductCard from "@/components/ProductCard";
import ProductModal from "@/components/ProductModal";
import { useToast } from "@/hooks/use-toast";

const Profile = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"preferences" | "wishlist">("preferences");
  const [profile, setProfile] = useState<OnboardingProfile | null>(getUserProfile());
  const [wishlistItems, setWishlistItems] = useState<Product[]>([]);
  const [loadingWishlist, setLoadingWishlist] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (!profile) {
      navigate("/onboarding");
    }
  }, [profile, navigate]);

  useEffect(() => {
    if (activeTab === "wishlist") {
      fetchWishlist();
    }
  }, [activeTab]);

  useEffect(() => {
    const handleSync = () => {
      if (activeTab === "wishlist") {
        fetchWishlist();
      }
    };
    window.addEventListener("storage", handleSync);
    window.addEventListener("skincares-wishlist-updated", handleSync);
    return () => {
      window.removeEventListener("storage", handleSync);
      window.removeEventListener("skincares-wishlist-updated", handleSync);
    };
  }, [activeTab]);

  const fetchWishlist = async () => {
    const ids = getWishlist();
    setLoadingWishlist(true);
    
    if (ids.length === 0) {
      setWishlistItems([]);
      setLoadingWishlist(false);
      return;
    }
    
    try {
      const products = await Promise.all(
        ids.map((id) => getProductDetail(id).catch(() => null))
      );
      setWishlistItems(products.filter((p): p is Product => p !== null));
    } catch (error) {
      console.error("Failed to fetch wishlist items", error);
    } finally {
      setLoadingWishlist(false);
    }
  };

  const handleUpdateProfile = <K extends keyof OnboardingProfile>(
    key: K, 
    val: OnboardingProfile[K]
  ) => {
    if (!profile) return;
    setProfile({ ...profile, [key]: val });
  };

  const toggleArray = (
    key: "concerns" | "ingredient_exclusions" | "product_interests", 
    val: Concern | IngredientExclusion | Category, 
    max?: number
  ) => {
    if (!profile) return;
    const arr = profile[key] as (Concern | IngredientExclusion | Category)[];
    if (arr.includes(val)) {
      handleUpdateProfile(key, arr.filter((v) => v !== val) as any);
    } else if (!max || arr.length < max) {
      handleUpdateProfile(key, [...arr, val] as any);
    }
  };

  const handleSavePreferences = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      const res = await submitOnboarding(profile);
      saveOnboardingForCurrentUser({
        recommendationUserId: res.user_id,
        profile,
      });
      toast({
        title: "Preferences saved",
        description: "Your skincare profile has been updated successfully.",
      });
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Error saving preferences",
        description: "Please try again later.",
      });
    } finally {
      setSaving(false);
    }
  };

  if (!profile) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background pb-20">
      <Navigation />
      
      <main className="container mx-auto max-w-4xl px-4 py-8">
        <header className="mb-8">
          <h1 className="font-display text-3xl font-bold text-foreground">My Profile</h1>
          <p className="text-muted-foreground">Manage your preferences and liked products.</p>
        </header>

        {/* Tabs */}
        <div className="mb-8 flex gap-2 rounded-2xl bg-muted p-1">
          <button
            onClick={() => setActiveTab("preferences")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium transition-all ${
              activeTab === "preferences"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Settings className="h-4 w-4" />
            Preferences
          </button>
          <button
            onClick={() => setActiveTab("wishlist")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium transition-all ${
              activeTab === "wishlist"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Heart className="h-4 w-4" />
            Liked Products
          </button>
        </div>

        <AnimatePresence mode="wait">
          {activeTab === "preferences" ? (
            <motion.div
              key="preferences"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-8"
            >
              {/* Skin Type */}
              <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
                <h2 className="mb-4 flex items-center gap-2 font-display text-xl font-bold">
                  <User className="h-5 w-5 text-primary" />
                  Skin Type
                </h2>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {SKIN_TYPES.map((st) => (
                    <button
                      key={st.value}
                      onClick={() => handleUpdateProfile("skin_type", st.value)}
                      className={`flex flex-col items-center gap-2 rounded-2xl border-2 p-4 transition-all ${
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
              </section>

              {/* Concerns */}
              <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
                <h2 className="mb-4 flex items-center gap-2 font-display text-xl font-bold">
                  <AlertCircle className="h-5 w-5 text-primary" />
                  Skin Concerns (up to 3)
                </h2>
                <div className="flex flex-wrap gap-2">
                  {CONCERNS.map((c) => (
                    <button
                      key={c.value}
                      onClick={() => toggleArray("concerns", c.value as Concern, 3)}
                      className={`rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                        profile.concerns.includes(c.value as Concern)
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "border border-border bg-card text-foreground hover:bg-muted"
                      }`}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </section>

              {/* Sensitivity */}
              <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
                <h2 className="mb-4 font-display text-xl font-bold">Sensitivity Level</h2>
                <div className="flex flex-col gap-2">
                  {SENSITIVITY_LEVELS.map((sl) => (
                    <button
                      key={sl.value}
                      onClick={() => handleUpdateProfile("sensitivity_level", sl.value)}
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
              </section>

              {/* Exclusions */}
              <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
                <h2 className="mb-4 font-display text-xl font-bold">Ingredients to Avoid</h2>
                <div className="flex flex-wrap gap-2">
                  {EXCLUSIONS.map((ex) => (
                    <button
                      key={ex.value}
                      onClick={() => toggleArray("ingredient_exclusions", ex.value as IngredientExclusion)}
                      className={`rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                        profile.ingredient_exclusions.includes(ex.value as IngredientExclusion)
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "border border-border bg-card text-foreground hover:bg-muted"
                      }`}
                    >
                      {ex.label}
                    </button>
                  ))}
                </div>
              </section>

              {/* Price Range */}
              <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
                <h2 className="mb-4 font-display text-xl font-bold">Price Range</h2>
                <div className="flex flex-col gap-2">
                  {PRICE_RANGES.map((pr) => (
                    <button
                      key={pr.value}
                      onClick={() => handleUpdateProfile("price_range", pr.value)}
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
              </section>

              {/* Routine Size */}
              <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
                <h2 className="mb-4 font-display text-xl font-bold">Routine Size</h2>
                <div className="grid grid-cols-2 gap-3">
                  {ROUTINE_SIZES.map((rs) => (
                    <button
                      key={rs.value}
                      onClick={() => handleUpdateProfile("routine_size", rs.value)}
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
              </section>

              {/* Product Interests */}
              <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
                <h2 className="mb-4 font-display text-xl font-bold">Product Interests (up to 3)</h2>
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
              </section>

              {/* Save Button */}
              <div className="sticky bottom-6 flex justify-center pt-4">
                <button
                  onClick={handleSavePreferences}
                  disabled={saving}
                  className="flex items-center gap-2 rounded-2xl bg-primary px-8 py-4 font-display text-lg font-bold text-primary-foreground shadow-lg transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
                >
                  {saving ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Save className="h-5 w-5" />
                  )}
                  {saving ? "Saving..." : "Save Preferences"}
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="wishlist"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              {loadingWishlist ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-64 animate-pulse rounded-2xl bg-muted" />
                  ))}
                </div>
              ) : wishlistItems.length > 0 ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {wishlistItems.map((product) => (
                    <ProductCard
                      key={product.product_id}
                      product={product}
                      onClick={() => setSelectedProduct(product)}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                    <Heart className="h-10 w-10 text-muted-foreground/30" />
                  </div>
                  <h3 className="text-xl font-bold text-foreground">No liked products yet</h3>
                  <p className="mt-2 text-muted-foreground">Products you heart will appear here.</p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <ProductModal
        product={selectedProduct}
        onClose={() => setSelectedProduct(null)}
      />
    </div>
  );
};

export default Profile;
