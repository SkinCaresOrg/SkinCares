import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ApiError, getRecommendations, getUserDebugState } from "@/lib/api";
import { RecommendedProduct, Category, Product } from "@/lib/types";
import { clearUserId, getUserId } from "@/lib/wishlist";
import { hydrateOnboardingForCurrentUser } from "@/lib/session";
import ProductCard from "@/components/ProductCard";
import ProductModal from "@/components/ProductModal";
import Navigation from "@/components/Navigation";
import { CATEGORIES, CATEGORY_LABELS } from "@/lib/types";
import { Sparkles, Frown, Zap } from "lucide-react";

const RECOMMENDATIONS_LIMIT = 60;

const Recommendations = () => {
  const navigate = useNavigate();
  const [category, setCategory] = useState<Category | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [debugState, setDebugState] = useState<any>(null);
  const [showDebug, setShowDebug] = useState(false);

  const userId = getUserId();

  const resolveRecommendationUserId = () => {
    if (userId) {
      return userId;
    }

    if (hydrateOnboardingForCurrentUser()) {
      return getUserId();
    }

    return null;
  };

  const resolvedUserId = resolveRecommendationUserId();

  const {
    data: recommendationsData,
    error: recommendationsError,
    isLoading,
    isFetching,
  } = useQuery({
    queryKey: ["recommendations", resolvedUserId, category, RECOMMENDATIONS_LIMIT],
    queryFn: () => getRecommendations(resolvedUserId as string, category || undefined, RECOMMENDATIONS_LIMIT),
    enabled: !!resolvedUserId,
    staleTime: 2 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });

  const products: RecommendedProduct[] = recommendationsData?.products ?? [];
  const groupedProducts = CATEGORIES.map((cat) => ({
    category: cat,
    items: products.filter((product) => product.category === cat).slice(0, 8),
  })).filter((group) => group.items.length > 0);

  useEffect(() => {
    if (!resolvedUserId) {
      navigate("/onboarding");
    }
  }, [resolvedUserId, navigate]);

  useEffect(() => {
    if (!(recommendationsError instanceof ApiError) || recommendationsError.status !== 404) {
      return;
    }
    clearUserId();
    navigate("/onboarding");
  }, [recommendationsError, navigate]);

  useEffect(() => {
    if (!resolvedUserId) {
      return;
    }

    getUserDebugState(resolvedUserId)
      .then((debug) => {
        setDebugState(debug);
      })
      .catch(() => {
        setDebugState(null);
      });
  }, [resolvedUserId, showDebug]);

  return (
    <div className="min-h-screen">
      <Navigation />
      <main className="container py-8">
        <div className="mb-8">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h1 className="font-display text-3xl font-bold text-foreground">For You</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Personalized recommendations based on your profile</p>
        </div>

        {/* Category filter */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setCategory(null)}
            className={`rounded-xl px-3.5 py-2 text-xs font-medium transition-all ${
              !category
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            }`}
          >
            All
          </button>
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat === category ? null : cat)}
              className={`rounded-xl px-3.5 py-2 text-xs font-medium transition-all ${
                category === cat
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
              }`}
            >
              {CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>

        {/* Debug Panel */}
        {showDebug && debugState && (
          <div className="mb-6 mt-6 rounded-lg border border-dashed border-yellow-300 bg-yellow-50 p-4">
            <h3 className="mb-2 flex items-center gap-2 font-semibold text-yellow-900">
              <Zap className="h-4 w-4" />
              Model Learning Status
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div>
                <div className="text-xs font-medium text-yellow-700">Total Interactions</div>
                <div className="text-xl font-bold text-yellow-900">{debugState.interactions}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-yellow-700">Liked</div>
                <div className="text-xl font-bold text-green-600">{debugState.liked_count}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-yellow-700">Disliked</div>
                <div className="text-xl font-bold text-red-600">{debugState.disliked_count}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-yellow-700">Model Ready</div>
                <div className="text-xl font-bold">{debugState.model_ready ? "✓" : "✗"}</div>
              </div>
            </div>
            <p className="mt-3 text-xs text-yellow-700">
              {debugState.model_ready 
                ? "Model is learning! Blue percentages below are ML scores."
                : "Need more feedback (at least 1 like + 1 dislike) for personalized scores."}
            </p>
          </div>
        )}
        <button
          onClick={() => setShowDebug(!showDebug)}
          className="mb-4 text-xs text-muted-foreground hover:text-foreground"
        >
          {showDebug ? "Hide" : "Show"} model debug info
        </button>

        {typeof debugState?.interactions === "number" && debugState.interactions < 5 && (
          <div className="mb-6 rounded-xl border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
            Swipe a few more products to improve your personalized recommendations.
          </div>
        )}

        <div className="mt-8">
          {isLoading ? (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-72 animate-pulse rounded-2xl bg-muted" />
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <Frown className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="mt-4 font-display text-lg font-semibold text-foreground">No recommendations yet</p>
              <p className="mt-1 text-sm text-muted-foreground">Try a different category filter</p>
            </div>
          ) : (
            <div className="space-y-8">
              {groupedProducts.map((group) => (
                <section key={group.category}>
                  <h2 className="mb-3 font-display text-xl font-bold text-foreground">
                    Best {CATEGORY_LABELS[group.category]}s for You
                  </h2>
                  <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    {group.items.map((product) => (
                      <div key={product.product_id} className="relative">
                        <ProductCard
                          key={product.product_id}
                          product={product}
                          onClick={setSelectedProduct}
                          explanation={product.explanation}
                          score={product.recommendation_score}
                          scoreLabel="Match"
                        />
                      </div>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}

          {isFetching && !isLoading && (
            <p className="mt-4 text-xs text-muted-foreground">Updating recommendations…</p>
          )}
        </div>
      </main>

      <ProductModal product={selectedProduct} onClose={() => setSelectedProduct(null)} />
    </div>
  );
};

export default Recommendations;
