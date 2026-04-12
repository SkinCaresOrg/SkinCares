import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Navigation from "@/components/Navigation";
import { Product, Category, Reaction, REACTION_TAGS, IRRITATION_TAGS, CATEGORY_LABELS, formatTagLabel, formatPrice } from "@/lib/types";
import { getProducts, submitFeedback } from "@/lib/api";
import { getUserId } from "@/lib/wishlist";
import { motion, useMotionValue, useTransform, AnimatePresence } from "framer-motion";
import { ThumbsUp, ThumbsDown, AlertTriangle, SkipForward, Undo2, Check } from "lucide-react";

const CATEGORY_GRADIENTS: Record<Category, string> = {
  cleanser: "from-sky-100 to-blue-50",
  moisturizer: "from-emerald-100 to-teal-50",
  sunscreen: "from-amber-100 to-yellow-50",
  treatment: "from-violet-100 to-purple-50",
  face_mask: "from-rose-100 to-pink-50",
  eye_cream: "from-indigo-100 to-blue-50",
};

type SwipeStep = "swipe" | "tags" | "submitting" | "done";

const SWIPE_THRESHOLD = 100;
const SWIPE_Y_THRESHOLD = -80;

const Swiping = () => {
  const navigate = useNavigate();
  const userId = getUserId();
  const [products, setProducts] = useState<Product[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [step, setStep] = useState<SwipeStep>("swipe");
  const [reaction, setReaction] = useState<Reaction | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [freeText, setFreeText] = useState("");
  const [loading, setLoading] = useState(true);
  const [direction, setDirection] = useState<"left" | "right" | "up" | "skip" | null>(null);
  const [offset, setOffset] = useState(0); // tracks how many products we've fetched so far
  const [hasMore, setHasMore] = useState(true); // false when backend says no more products

// Load seen product IDs from localStorage so we don't show them again after refresh
  const [seenIds] = useState<Set<number>>(() => {
  const stored = localStorage.getItem("skincares_seen_products");
  return stored ? new Set(JSON.parse(stored)) : new Set();
});



  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-15, 15]);
  const likeOpacity = useTransform(x, [0, SWIPE_THRESHOLD], [0, 1]);
  const dislikeOpacity = useTransform(x, [-SWIPE_THRESHOLD, 0], [1, 0]);
  const irritationOpacity = useTransform(y, [SWIPE_Y_THRESHOLD, 0], [1, 0]);
  const skipOpacity = useTransform(
    [x, y] as any,
    ([latestX, latestY]: number[]) => {
      // only show SKIP if dragging mostly downward, not sideways
      if (Math.abs(latestX) > 30) return 0;
      return Math.min(1, Math.max(0, latestY / 80));
    }
  );

useEffect(() => {
    if (!userId) {
      navigate("/onboarding");
      return;
    }
    // Initial load — fetch first 24 products
    getProducts({ offset: 0 }).then((res) => {
      setProducts(res.products.filter(p => !seenIds.has(p.product_id)));
      setOffset(res.products.length);
      // if backend returned fewer than 24, there are no more pages
      setHasMore(res.products.length === 24);
      setLoading(false);
    });
}, [userId, navigate]);

// Load more products when we are 5 cards from the end
// This prevents showing "All done" too early and keeps the queue full
useEffect(() => {
    if (!hasMore || loading) return;
    if (currentIndex >= products.length - 5) {
      setLoading(true);
      getProducts({offset}).then((res) => {
        if (res.products.length === 0) {
          // No more products available from the backend
          setHasMore(false);
        } else {
          // Append new products to the existing list, never resetting to page 1
          setProducts((prev) => [...prev, ...res.products.filter(p => !seenIds.has(p.product_id))]);
          setOffset((prev) => prev + res.products.length);
          setHasMore(res.products.length === 24);
        }
        setLoading(false);
      });
    }
}, [currentIndex, products.length, offset, hasMore, loading]);

  // Reset motion values when moving to next product
  useEffect(() => {
    x.set(0);
    y.set(0);
  }, [currentIndex, x, y]);

  const currentProduct = products[currentIndex];
  const isFinished = currentIndex >= products.length && !loading;

  const resetCardState = useCallback(() => {
    setReaction(null);
    setSelectedTags([]);
    setFreeText("");
    setStep("swipe");
    setDirection(null);
  }, []);

  const handleReaction = useCallback(async (r: Reaction | "skip") => {
    if (!currentProduct || !userId) return;

    if (r === "skip") {
      setDirection("skip");
      setStep("submitting"); 

      // Persist seen product
      const updated = Array.from(seenIds).concat(currentProduct.product_id);
      localStorage.setItem("skincares_seen_products", JSON.stringify(updated));
      seenIds.add(currentProduct.product_id);

      // Fire in background — no await so animation isn't blocked
      submitFeedback({ user_id: userId, product_id: currentProduct.product_id, has_tried: false });

      setTimeout(() => {
        setCurrentIndex((i) => i + 1);
        resetCardState();
      }, 300);
      return;
    }

    setReaction(r);
    setDirection(r === "like" ? "right" : r === "dislike" ? "left" : "up");
    setStep("tags");
  }, [currentProduct, userId, resetCardState]);

  const handleDragEnd = useCallback((_: any, info: { offset: { x: number; y: number } }) => {
  if (info.offset.y < SWIPE_Y_THRESHOLD) {
    handleReaction("irritation");
  } else if (info.offset.y > 80) {  // ← ADD THIS
    handleReaction("skip");
  } else if (info.offset.x > SWIPE_THRESHOLD) {
    handleReaction("like");
  } else if (info.offset.x < -SWIPE_THRESHOLD) {
    handleReaction("dislike");
  }
}, [handleReaction]);

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) => prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]);
  };

  const handleSubmitTags = async () => {
    if (!currentProduct || !userId || !reaction) return;
    setStep("submitting");
    await submitFeedback({
      user_id: userId,
      product_id: currentProduct.product_id,
      has_tried: true,
      reaction,
      reason_tags: selectedTags,
      free_text: freeText,
    });
    setStep("done");
    if (currentProduct) {
    const updated = Array.from(seenIds).concat(currentProduct.product_id);
    localStorage.setItem("skincares_seen_products", JSON.stringify(updated));
    seenIds.add(currentProduct.product_id);
  }
      setTimeout(() => {
        setCurrentIndex((i) => i + 1);
        resetCardState();
      }, 800);
    };

  const getTags = (): string[] => {
    if (!reaction || !currentProduct) return [];
    if (reaction === "irritation") return IRRITATION_TAGS;
    const catTags = REACTION_TAGS[currentProduct.category];
    return reaction === "like" ? catTags.like : catTags.dislike;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <div className="flex items-center justify-center" style={{ height: "calc(100vh - 4rem)" }}>
          <div className="flex flex-col items-center gap-3">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-muted border-t-primary" />
            <p className="text-sm text-muted-foreground">Loading products…</p>
          </div>
        </div>
      </div>
    );
  }

  if (isFinished) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <div className="flex items-center justify-center" style={{ height: "calc(100vh - 4rem)" }}>
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-success/10">
              <Check className="h-8 w-8 text-success" />
            </div>
            <h2 className="font-display text-2xl font-bold text-foreground">All done!</h2>
            <p className="max-w-xs text-sm text-muted-foreground">You've reviewed all available products. Check back later for new ones.</p>
            <button
              onClick={() => navigate("/recommendations")}
              className="mt-2 rounded-xl bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              See Your Recommendations
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="container max-w-md py-6">
        {/* Progress */}
        <div className="mb-4 flex items-center justify-center">
        <p className="text-xs font-medium text-muted-foreground">
          {currentIndex + 1} reviewed
        </p>
      </div>

        {/* Card area */}
        <div className="relative flex items-center justify-center" style={{ minHeight: 420 }}>
          <AnimatePresence mode="wait">
            {step === "swipe" && currentProduct && (
              <motion.div
                key={currentProduct.product_id}
                className="w-full cursor-grab active:cursor-grabbing"
                style={{ x, y, rotate }}
                drag
                dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
                dragElastic={0.8}
                onDragEnd={handleDragEnd}
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{
                    x: direction === "right" ? 300 : direction === "left" ? -300 : 0,
                    y: direction === "up" ? -300 : direction === "skip" ? 300 : 0,
                  opacity: 0,
                  transition: { duration: 0.3 },
                }}
              >
                {/* Swipe indicator overlays */}
                <motion.div
                  className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-3xl border-4 border-success bg-success/5"
                  style={{ opacity: likeOpacity }}
                >
                  <span className="rounded-xl bg-success px-4 py-2 text-lg font-bold text-white -rotate-12">LIKE</span>
                </motion.div>
                <motion.div
                  className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-3xl border-4 border-warning bg-warning/5"
                  style={{ opacity: dislikeOpacity }}
                >
                  <span className="rounded-xl bg-warning px-4 py-2 text-lg font-bold text-white rotate-12">NOPE</span>
                </motion.div>
                <motion.div
                  className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-3xl border-4 border-destructive bg-destructive/5"
                  style={{ opacity: irritationOpacity }}
                >
                  <span className="rounded-xl bg-destructive px-4 py-2 text-lg font-bold text-white">IRRITATION</span>
                </motion.div>
                {/* Skip indicator overlay */}
              <motion.div
                  className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-3xl border-4 border-gray-400 bg-gray-400/5"
                  style={{ opacity: skipOpacity }}
                >
                  <span className="rounded-xl bg-gray-400 px-4 py-2 text-lg font-bold text-white">SKIP</span>
                </motion.div>

                {/* Product card */}
                <div className="overflow-hidden rounded-3xl border border-border bg-card shadow-lg">
                  <div className={`relative flex h-48 items-center justify-center bg-gradient-to-br ${CATEGORY_GRADIENTS[currentProduct.category]} overflow-hidden`}>
                    {currentProduct.image_url && currentProduct.image_url.trim().length > 0 ? (
                      <img
                        src={currentProduct.image_url}
                        alt={currentProduct.product_name}
                        className="h-full w-full object-cover object-center"
                        onError={(e) => {
                          e.currentTarget.style.display = "none";
                        }}
                      />
                    ) : (
                      <span className="font-display text-4xl font-bold text-foreground/10">
                        {CATEGORY_LABELS[currentProduct.category]}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col gap-2 p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="font-display text-lg font-bold text-foreground">{currentProduct.product_name}</h2>
                        <p className="text-sm text-muted-foreground">{currentProduct.brand}</p>
                      </div>
                      <span className="whitespace-nowrap font-display text-lg font-bold text-primary">
                        {formatPrice(currentProduct.price)}
                      </span>
                    </div>
                    <span className="inline-flex w-fit rounded-lg bg-secondary/50 px-2.5 py-1 text-xs font-medium text-secondary-foreground">
                      {CATEGORY_LABELS[currentProduct.category]}
                    </span>
                    {currentProduct.short_description && (
                      <p className="text-sm text-muted-foreground">{currentProduct.short_description}</p>
                    )}
                  </div>
                </div>
              </motion.div>
            )}

            {step === "tags" && currentProduct && (
              <motion.div
                key="tags"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="w-full rounded-3xl border border-border bg-card p-6 shadow-lg"
              >
                <div className="mb-1 flex items-center gap-2">
                  {reaction === "like" && <ThumbsUp className="h-5 w-5 text-success" />}
                  {reaction === "dislike" && <ThumbsDown className="h-5 w-5 text-warning" />}
                  {reaction === "irritation" && <AlertTriangle className="h-5 w-5 text-destructive" />}
                  <h3 className="font-display text-base font-bold text-foreground">
                    {currentProduct.product_name}
                  </h3>
                </div>
                <p className="mb-4 text-sm text-muted-foreground">Tell us more (select all that apply):</p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {getTags().map((tag) => (
                    <button
                      key={tag}
                      onClick={() => toggleTag(tag)}
                      className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-all ${
                        selectedTags.includes(tag)
                          ? "bg-primary text-primary-foreground"
                          : "border border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      {formatTagLabel(tag)}
                    </button>
                  ))}
                </div>
                <textarea
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  placeholder="Any other thoughts? (optional)"
                  className="mb-4 h-20 w-full resize-none rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10"
                />
                <button
                  onClick={handleSubmitTags}
                  className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Submit & Next
                </button>
              </motion.div>
            )}

            {(step === "submitting" || step === "done") && (
              <motion.div
                key="done"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-2 py-12"
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
                  <Check className="h-7 w-7 text-success" />
                </div>
                <p className="font-display text-sm font-semibold text-foreground">Feedback saved!</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Action buttons (visible during swipe step) */}
        {step === "swipe" && currentProduct && (
          <div className="mt-6 flex items-center justify-center gap-4">
            <button
              onClick={() => handleReaction("dislike")}
              className="flex h-14 w-14 items-center justify-center rounded-full border border-border bg-card shadow-sm transition-all hover:border-warning hover:bg-warning/5 hover:shadow-md"
              title="Dislike"
            >
              <ThumbsDown className="h-5 w-5 text-warning" />
            </button>
            <button
              onClick={() => handleReaction("irritation")}
              className="flex h-12 w-12 items-center justify-center rounded-full border border-border bg-card shadow-sm transition-all hover:border-destructive hover:bg-destructive/5 hover:shadow-md"
              title="Caused irritation"
            >
              <AlertTriangle className="h-4 w-4 text-destructive" />
            </button>
            <button
              onClick={() => handleReaction("like")}
              className="flex h-14 w-14 items-center justify-center rounded-full border border-border bg-card shadow-sm transition-all hover:border-success hover:bg-success/5 hover:shadow-md"
              title="Like"
            >
              <ThumbsUp className="h-5 w-5 text-success" />
            </button>
            <button
              onClick={() => handleReaction("skip")}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-card shadow-sm transition-all hover:bg-muted hover:shadow-md"
              title="Haven't tried / Skip"
            >
              <SkipForward className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>
        )}

        {/* Hint */}
        {step === "swipe" && (
          <p className="mt-4 text-center text-xs text-muted-foreground">
            Drag right to like · left to dislike · up for irritation · down to skip 
             or use the buttons
          </p>
        )}

    
      </div>
    </div>
  );
};

export default Swiping;
