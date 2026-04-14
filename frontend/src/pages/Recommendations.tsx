import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, getRecommendations, getUserDebugState } from "@/lib/api";
import { RecommendedProduct, Category, Product } from "@/lib/types";
import { clearUserId, getUserId } from "@/lib/wishlist";
import ProductCard from "@/components/ProductCard";
import ProductModal from "@/components/ProductModal";
import Navigation from "@/components/Navigation";
import { CATEGORIES, CATEGORY_LABELS } from "@/lib/types";
import { Sparkles, Frown } from "lucide-react";

const PAGE_SIZE = 9;

const Recommendations = () => {
  const navigate = useNavigate();

  const [allProducts, setAllProducts] = useState<RecommendedProduct[]>([]);
  const [visibleProducts, setVisibleProducts] = useState<RecommendedProduct[]>([]);

  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState<Category | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [debugState, setDebugState] = useState<any>(null);

  const [page, setPage] = useState(0);

  const userId = getUserId();

  useEffect(() => {
    if (!userId) {
      navigate("/onboarding");
      return;
    }

    setLoading(true);
    setPage(0);

    Promise.all([
      getRecommendations(userId, category || undefined),
      getUserDebugState(userId),
    ])
      .then(([res, debug]) => {
        setAllProducts(res.products);
        setDebugState(debug);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) {
          clearUserId();
          navigate("/onboarding");
        }
      })
      .finally(() => setLoading(false));
  }, [userId, category, navigate]);

  useEffect(() => {
    const end = (page + 1) * PAGE_SIZE;
    setVisibleProducts(allProducts.slice(0, end));
  }, [allProducts, page]);

  const hasMore = visibleProducts.length < allProducts.length;

  return (
    <div className="min-h-screen">
      <Navigation />

      <main className="container py-8">
        <div className="mb-8">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h1 className="font-display text-3xl font-bold text-foreground">
              For You
            </h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Personalized recommendations based on your profile
          </p>
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

        <div className="mt-8">
          {loading ? (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-72 animate-pulse rounded-2xl bg-muted" />
              ))}
            </div>
          ) : visibleProducts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <Frown className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="mt-4 font-display text-lg font-semibold text-foreground">
                No recommendations yet
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Try a different category filter
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {visibleProducts.map((product) => (
                  <ProductCard
                    key={product.product_id}
                    product={product}
                    onClick={setSelectedProduct}
                    explanation={product.explanation}
                  />
                ))}
              </div>

              {hasMore && (
                <div className="mt-8 flex justify-center">
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    className="rounded-xl bg-primary px-5 py-2 text-sm font-medium text-white"
                  >
                    Load more
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      <ProductModal
        product={selectedProduct}
        onClose={() => setSelectedProduct(null)}
      />
    </div>
  );
};

export default Recommendations;