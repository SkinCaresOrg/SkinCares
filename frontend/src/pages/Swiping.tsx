import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Navigation from "@/components/Navigation";
import { Product, Category, Reaction, REACTION_TAGS, IRRITATION_TAGS, CATEGORY_LABELS, formatTagLabel, formatPrice } from "@/lib/types";
import { getProducts, submitFeedback } from "@/lib/api";
import { getUserId } from "@/lib/wishlist";
import { motion, useMotionValue, useTransform, AnimatePresence } from "framer-motion";
import { ThumbsUp, ThumbsDown, AlertTriangle, Zap, Check } from "lucide-react";

const CATEGORY_GRADIENTS: Record<Category, string> = {
  cleanser: "from-sky-100 to-blue-50",
  moisturizer: "from-emerald-100 to-teal-50",
  sunscreen: "from-amber-100 to-yellow-50",
  treatment: "from-violet-100 to-purple-50",
  face_mask: "from-rose-100 to-pink-50",
  eye_cream: "from-indigo-100 to-blue-50",
};

type SwipeStep = "swipe" | "tags" | "submitting" | "done";
type SwipeDirection = "like" | "dislike" | "haven_tried" | "irritation" | null;
type ProductWithIngredients = Product & { ingredients?: string[]; ingredient_highlights?: string[] };

const SWIPE_THRESHOLD = 80;
const SWIPE_Y_THRESHOLD = 80;

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
  const [direction, setDirection] = useState<SwipeDirection>(null);

  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const rotate = useTransform(x, [-150, 150], [-25, 25]);
  const likeOpacity = useTransform(x, [0, SWIPE_THRESHOLD], [0, 1]);
  const dislikeOpacity = useTransform(x, [-SWIPE_THRESHOLD, 0], [1, 0]);
  const irritationOpacity = useTransform(y, [-SWIPE_Y_THRESHOLD, 0], [1, 0]);
  const haventTriedOpacity = useTransform(y, [0, SWIPE_Y_THRESHOLD], [0, 1]);
  const likeScale = useTransform(x, [0, SWIPE_THRESHOLD], [0.5, 1]);
  const dislikeScale = useTransform(x, [-SWIPE_THRESHOLD, 0], [1, 0.5]);
  const irritationScale = useTransform(y, [-SWIPE_Y_THRESHOLD, 0], [1, 0.5]);
  const haventTriedScale = useTransform(y, [0, SWIPE_Y_THRESHOLD], [0.5, 1]);

  useEffect(() => {
    if (!userId) {
      navigate("/onboarding");
      return;
    }
    getProducts({}).then((res) => {
      setProducts(res.products);
      setLoading(false);
    });
  }, [userId, navigate]);

  const currentProduct = products[currentIndex];
  const isFinished = currentIndex >= products.length && !loading;

  const resetCardState = useCallback(() => {
    setReaction(null);
    setSelectedTags([]);
    setFreeText("");
    setStep("swipe");
    setDirection(null);
  }, []);

  const handleReaction = useCallback(
    async (r: Reaction | "haven_tried") => {
      if (!currentProduct || !userId) return;

      if (r === "haven_tried") {
        setDirection("haven_tried");
        await submitFeedback({ user_id: userId, product_id: currentProduct.product_id, has_tried: false });
        setTimeout(() => {
          setCurrentIndex((i) => i + 1);
          resetCardState();
        }, 300);
        return;
      }

      setReaction(r);
      setDirection(r === "like" ? "like" : r === "dislike" ? "dislike" : "irritation");
      setStep("tags");
    },
    [currentProduct, userId, resetCardState],
  );

  const handleDragEnd = useCallback(
    (_: any, info: { offset: { x: number; y: number } }) => {
      if (info.offset.y > SWIPE_Y_THRESHOLD) {
        handleReaction("haven_tried");
      } else if (info.offset.y < -SWIPE_Y_THRESHOLD) {
        handleReaction("irritation");
      } else if (info.offset.x > SWIPE_THRESHOLD) {
        handleReaction("like");
      } else if (info.offset.x < -SWIPE_THRESHOLD) {
        handleReaction("dislike");
      }
    },
    [handleReaction],
  );

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));
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
      free_text: freeText || undefined,
    });
    setStep("done");
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

  const getKeyIngredients = (product: Product): string[] => {
    const withIngredients = product as ProductWithIngredients;
    const source =
      withIngredients.ingredient_highlights && withIngredients.ingredient_highlights.length > 0
        ? withIngredients.ingredient_highlights
        : withIngredients.ingredients ?? [];

    return source
      .map((ing) => ing.trim())
      .filter((ing) => ing.length > 0)
      .filter((ing, index, list) => list.findIndex((item) => item.toLowerCase() === ing.toLowerCase()) === index)
      .slice(0, 6);
  };

  const keyIngredients = currentProduct ? getKeyIngredients(currentProduct) : [];
  const visibleIngredients = keyIngredients.slice(0, 3);
  const extraIngredientCount = Math.max(keyIngredients.length - visibleIngredients.length, 0);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-background via-background to-muted/10">
        <Navigation />
        <div className="flex items-center justify-center" style={{ height: "calc(100vh - 4rem)" }}>
          <div className="flex flex-col items-center gap-3">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-muted border-t-primary" />
            <p className="text-xs text-muted-foreground">Loading products…</p>
          </div>
        </div>
      </div>
    );
  }

  if (isFinished) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-background via-background to-muted/10">
        <Navigation />
        <div className="flex items-center justify-center" style={{ height: "calc(100vh - 4rem)" }}>
          <div className="flex flex-col items-center gap-4 text-center">
            <motion.div
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="flex h-16 w-16 items-center justify-center rounded-full bg-success/10"
            >
              <Check className="h-8 w-8 text-success" />
            </motion.div>
            <h2 className="font-display text-xl font-bold text-foreground">All done!</h2>
            <p className="max-w-xs text-sm text-muted-foreground">You've reviewed all products</p>
            <button
              onClick={() => navigate("/recommendations")}
              className="mt-4 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              See Recommendations
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background via-background to-muted/10 flex flex-col">
      <Navigation />

      <div className="flex-1 flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-xs mb-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs font-medium text-muted-foreground/70">
              {currentIndex + 1}/{products.length}
            </span>
            <span className="text-xs text-muted-foreground/50">SkinCares</span>
          </div>
          <div className="h-0.5 bg-muted rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-primary"
              initial={{ width: 0 }}
              animate={{ width: `${((currentIndex + 1) / products.length) * 100}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
        </div>

        <div className="relative w-full max-w-sm mx-auto">
          <AnimatePresence mode="wait">
            {step === "swipe" && currentProduct && (
              <>
                {currentIndex + 2 < products.length && (
                  <div
                    className="absolute inset-0 rounded-2xl border border-border/15 bg-card/60 shadow-none pointer-events-none"
                    style={{ transform: "scale(0.92) translateY(10px)", transformOrigin: "center top" }}
                  />
                )}

                {currentIndex + 1 < products.length && (
                  <div
                    className="absolute inset-0 rounded-2xl border border-border/25 bg-card/85 shadow-sm pointer-events-none"
                    style={{ transform: "scale(0.96) translateY(5px)", transformOrigin: "center top" }}
                  />
                )}

                <motion.div
                  key={currentProduct.product_id}
                  className="relative z-20 w-full cursor-grab active:cursor-grabbing"
                  style={{ x, y, rotate }}
                  drag
                  dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
                  dragElastic={0.15}
                  onDragEnd={handleDragEnd}
                  initial={{ scale: 0.95, opacity: 0, y: 20 }}
                  animate={{ scale: 1, opacity: 1, y: 0 }}
                  exit={{
                    x: direction === "like" ? 500 : direction === "dislike" ? -500 : 0,
                    y: direction === "irritation" ? -500 : direction === "haven_tried" ? 500 : 0,
                    opacity: 0,
                    rotate: direction === "like" ? 45 : direction === "dislike" ? -45 : 0,
                    transition: { duration: 0.5, ease: "easeIn" },
                  }}
                >
                  <div className="relative overflow-hidden rounded-2xl border border-border/50 bg-card shadow-2xl ring-1 ring-black/[0.03]">
                    <div className={`relative flex h-96 items-center justify-center bg-gradient-to-br ${CATEGORY_GRADIENTS[currentProduct.category]} overflow-hidden`}>
                      <div className="absolute inset-0 opacity-5">
                        <div
                          className="absolute inset-0"
                          style={{
                            backgroundImage: "radial-gradient(circle, currentColor 1px, transparent 1px)",
                            backgroundSize: "20px 20px",
                          }}
                        />
                      </div>

                      <div className="relative text-center z-10">
                        <span className="inline-block rounded-full bg-white/20 backdrop-blur-md px-4 py-2 text-xs font-semibold text-white/90">
                          {CATEGORY_LABELS[currentProduct.category]}
                        </span>
                      </div>
                    </div>

                    <div className="px-5 py-4 space-y-2">
                      <h2 className="font-display text-lg font-bold text-foreground leading-tight">{currentProduct.product_name}</h2>
                      <p className="text-sm text-muted-foreground/80">{currentProduct.brand}</p>
                      <div className="flex items-baseline justify-between pt-1">
                        <span className="text-2xl font-bold text-primary">{formatPrice(currentProduct.price)}</span>
                      </div>
                      {visibleIngredients.length > 0 && (
                        <div className="pt-2">
                          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">
                            Key ingredients
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {visibleIngredients.map((ingredient) => (
                              <span
                                key={ingredient}
                                className="rounded-full border border-border/60 bg-muted/35 px-2 py-0.5 text-[11px] font-medium text-foreground/85"
                              >
                                {ingredient}
                              </span>
                            ))}
                            {extraIngredientCount > 0 && (
                              <span className="rounded-full border border-border/60 bg-muted/20 px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                                +{extraIngredientCount} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <motion.div className="pointer-events-none absolute inset-0 flex items-center justify-center" style={{ opacity: likeOpacity }}>
                    <motion.div style={{ scale: likeScale }} className="text-center">
                      <div className="text-6xl font-black text-success drop-shadow-lg">LIKE</div>
                      <ThumbsUp className="h-10 w-10 text-success mx-auto mt-2 drop-shadow-lg" />
                    </motion.div>
                  </motion.div>

                  <motion.div className="pointer-events-none absolute inset-0 flex items-center justify-center" style={{ opacity: dislikeOpacity }}>
                    <motion.div style={{ scale: dislikeScale }} className="text-center">
                      <div className="text-6xl font-black text-warning drop-shadow-lg">DISLIKE</div>
                      <ThumbsDown className="h-10 w-10 text-warning mx-auto mt-2 drop-shadow-lg" />
                    </motion.div>
                  </motion.div>

                  <motion.div className="pointer-events-none absolute inset-0 flex items-center justify-center" style={{ opacity: irritationOpacity }}>
                    <motion.div style={{ scale: irritationScale }} className="text-center">
                      <div className="text-6xl font-black text-destructive drop-shadow-lg">IRRITATION</div>
                      <AlertTriangle className="h-10 w-10 text-destructive mx-auto mt-2 drop-shadow-lg" />
                    </motion.div>
                  </motion.div>

                  <motion.div className="pointer-events-none absolute inset-0 flex items-center justify-center" style={{ opacity: haventTriedOpacity }}>
                    <motion.div style={{ scale: haventTriedScale }} className="text-center">
                      <div className="text-4xl font-black text-blue-600 drop-shadow-lg">HAVEN’T TRIED</div>
                      <Zap className="h-10 w-10 text-blue-600 mx-auto mt-2 drop-shadow-lg" />
                    </motion.div>
                  </motion.div>
                </motion.div>
              </>
            )}

            {step === "tags" && currentProduct && (
              <motion.div
                key="tags"
                initial={{ opacity: 0, y: 30, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 30, scale: 0.95 }}
                className="w-full max-w-sm rounded-2xl border border-border/40 bg-card p-5 shadow-xl"
              >
                <div className="mb-4 flex items-center gap-2">
                  {reaction === "like" && <ThumbsUp className="h-5 w-5 text-success" />}
                  {reaction === "dislike" && <ThumbsDown className="h-5 w-5 text-warning" />}
                  {reaction === "irritation" && <AlertTriangle className="h-5 w-5 text-destructive" />}
                  <h3 className="font-display text-base font-bold text-foreground line-clamp-1">{currentProduct.product_name}</h3>
                </div>

                <p className="mb-3 text-xs font-medium text-muted-foreground">Details:</p>

                <div className="flex flex-wrap gap-1.5 mb-4">
                  {getTags().map((tag) => (
                    <button
                      key={tag}
                      onClick={() => toggleTag(tag)}
                      className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
                        selectedTags.includes(tag)
                          ? "bg-primary text-primary-foreground"
                          : "border border-border/50 bg-muted/30 text-muted-foreground hover:bg-muted/60"
                      }`}
                    >
                      {formatTagLabel(tag)}
                    </button>
                  ))}
                </div>

                <textarea
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  placeholder="Notes (optional)"
                  className="mb-4 h-16 w-full resize-none rounded-lg border border-border/50 bg-background/50 px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground/50 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/20"
                />

                <button
                  onClick={handleSubmitTags}
                  className="w-full rounded-lg bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground transition-all hover:bg-primary/90 active:scale-95"
                >
                  Save
                </button>
              </motion.div>
            )}

            {(step === "submitting" || step === "done") && (
              <motion.div
                key="done"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-2"
              >
                <motion.div
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 0.5 }}
                  className="flex h-12 w-12 items-center justify-center rounded-full bg-success/15"
                >
                  <Check className="h-6 w-6 text-success" />
                </motion.div>
                <p className="text-xs font-semibold text-muted-foreground">Saved</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {step === "swipe" && currentProduct && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="mt-6 flex items-center justify-center gap-2"
          >
            <motion.button
              whileHover={{ scale: 1.15 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => handleReaction("dislike")}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-warning/40 bg-warning/10 text-warning/80 transition-colors hover:border-warning/60 hover:bg-warning/15 hover:text-warning"
              title="Dislike"
            >
              <ThumbsDown className="h-5 w-5" />
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.15 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => handleReaction("haven_tried")}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-blue-400/40 bg-blue-50/30 text-blue-600/80 transition-colors hover:border-blue-400/60 hover:bg-blue-50/50 hover:text-blue-600"
              title="Haven't Tried"
            >
              <Zap className="h-5 w-5" />
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.15 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => handleReaction("like")}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-success/40 bg-success/10 text-success/80 transition-colors hover:border-success/60 hover:bg-success/15 hover:text-success"
              title="Like"
            >
              <ThumbsUp className="h-5 w-5" />
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.15 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => handleReaction("irritation")}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-destructive/40 bg-destructive/10 text-destructive/80 transition-colors hover:border-destructive/60 hover:bg-destructive/15 hover:text-destructive"
              title="Irritation"
            >
              <AlertTriangle className="h-5 w-5" />
            </motion.button>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default Swiping;
