import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  ThumbsDown,
  ThumbsUp,
  Loader2,
  Check,
  ArrowRight,
} from "lucide-react";

import Navigation from "@/components/Navigation";
import WishlistButton from "@/components/WishlistButton";
import {
  createSwipe,
  getSwipeQueue,
  submitSwipeQuestionnaire,
} from "@/lib/api";
import { CATEGORY_LABELS, Product } from "@/lib/types";

const PRELOAD_THRESHOLD = 5;
const FETCH_SIZE = 6;
const SWIPE_X_THRESHOLD = 100;

type SwipeReaction = "like" | "dislike";
type SwipeStep = "swipe" | "questionnaire" | "submitting";

const LIKE_OPTIONS = [
  "Suits my skin type",
  "Love the ingredients",
  "Good price point",
  "Heard great reviews",
  "Love the brand",
  "Other",
];

const DISLIKE_OPTIONS = [
  "Contains fragrance",
  "Too expensive",
  "Wrong skin type for me",
  "Contains an ingredient I avoid",
  "Bad reviews",
  "Not interested in this category",
  "Other",
];

const Swiping = () => {
  const navigate = useNavigate();
  const [queue, setQueue] = useState<Product[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [step, setStep] = useState<SwipeStep>("swipe");
  const [reaction, setReaction] = useState<SwipeReaction | null>(null);
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [freeText, setFreeText] = useState("");
  const [currentSwipeEventId, setCurrentSwipeEventId] = useState<number | null>(null);
  const [direction, setDirection] = useState<"left" | "right" | null>(null);
  const isFetchingQueue = useRef(false);

  const currentProduct = queue[currentIndex];

  const availableReasons = useMemo(
    () => (reaction === "like" ? LIKE_OPTIONS : DISLIKE_OPTIONS),
    [reaction]
  );

  const fetchQueue = useCallback(
    async (reset = false) => {
      if (isFetchingQueue.current) return;
      if (!reset && !hasMore) return;

      isFetchingQueue.current = true;
      setLoadingQueue(true);
      try {
        const payload = await getSwipeQueue(FETCH_SIZE);
        setQueue((prev) => (reset ? payload.products : [...prev, ...payload.products]));
        setHasMore(payload.hasMore);
        if (reset) {
          setCurrentIndex(0);
        }
      } finally {
        setLoadingQueue(false);
        isFetchingQueue.current = false;
      }
    },
    [hasMore]
  );

  useEffect(() => {
    void fetchQueue(true);
  }, [fetchQueue]);

  useEffect(() => {
    const remainingInMemory = queue.length - currentIndex - 1;
    if (remainingInMemory <= PRELOAD_THRESHOLD && hasMore && !loadingQueue) {
      void fetchQueue(false);
    }
  }, [queue.length, currentIndex, hasMore, loadingQueue, fetchQueue]);

  const moveToNextProduct = useCallback(() => {
    setCurrentIndex((prev) => prev + 1);
    setStep("swipe");
    setReaction(null);
    setSelectedReasons([]);
    setFreeText("");
    setCurrentSwipeEventId(null);
    setDirection(null);
  }, []);

  const handleSwipe = useCallback(
    async (nextReaction: SwipeReaction) => {
      if (!currentProduct) return;
      setDirection(nextReaction === "like" ? "right" : "left");
      const swipe = await createSwipe(
        currentProduct.product_id,
        nextReaction === "like" ? "like" : "dislike"
      );
      setCurrentSwipeEventId(swipe.swipe_event_id);
      setReaction(nextReaction);
      setStep("questionnaire");
    },
    [currentProduct]
  );

  const handleQuestionnaireSubmit = useCallback(
    async (skip: boolean) => {
      if (!currentSwipeEventId) return;
      setStep("submitting");
      await submitSwipeQuestionnaire(currentSwipeEventId, {
        skipped: skip,
        reason_tags: skip ? [] : selectedReasons,
        free_text: skip ? "" : freeText,
      });
      moveToNextProduct();
    },
    [currentSwipeEventId, selectedReasons, freeText, moveToNextProduct]
  );

  const handleDragEnd = useCallback(
    async (_: unknown, info: { offset: { x: number } }) => {
      if (step !== "swipe") return;
      if (info.offset.x > SWIPE_X_THRESHOLD) {
        await handleSwipe("like");
      } else if (info.offset.x < -SWIPE_X_THRESHOLD) {
        await handleSwipe("dislike");
      }
    },
    [step, handleSwipe]
  );

  const toggleReason = (reason: string) => {
    setSelectedReasons((prev) =>
      prev.includes(reason) ? prev.filter((item) => item !== reason) : [...prev, reason]
    );
  };

  const isFinished = !loadingQueue && !currentProduct && !hasMore;

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="container max-w-xl py-6">
        {loadingQueue && !currentProduct ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Loading your swipe queue…</p>
          </div>
        ) : isFinished ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-success/10">
              <Check className="h-8 w-8 text-success" />
            </div>
            <h2 className="font-display text-2xl font-bold text-foreground">All done!</h2>
            <p className="max-w-sm text-sm text-muted-foreground">
              You&apos;ve reviewed all available products.
            </p>
            <button
              onClick={() => navigate("/recommendations")}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-medium text-primary-foreground"
            >
              See Your Recommendations <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <>
            <div className="mb-4 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {Math.min(currentIndex + 1, queue.length)} / {queue.length}
              </span>
              {loadingQueue && <span>Preloading next products…</span>}
            </div>

            <AnimatePresence mode="wait">
              {step === "swipe" && currentProduct && (
                <motion.div
                  key={currentProduct.product_id}
                  drag="x"
                  dragElastic={0.8}
                  dragConstraints={{ left: 0, right: 0 }}
                  onDragEnd={handleDragEnd}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{
                    x: direction === "right" ? 300 : direction === "left" ? -300 : 0,
                    opacity: 0,
                    transition: { duration: 0.25 },
                  }}
                  className="overflow-hidden rounded-3xl border border-border bg-card shadow-lg"
                >
                  <div className="relative h-56 bg-muted">
                    {currentProduct.image_url ? (
                      <img
                        src={currentProduct.image_url}
                        alt={currentProduct.product_name}
                        className="h-full w-full object-cover"
                      />
                    ) : null}
                    <div className="absolute right-3 top-3">
                      <WishlistButton productId={currentProduct.product_id} />
                    </div>
                  </div>

                  <div className="space-y-3 p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h2 className="font-display text-xl font-bold text-foreground">
                          {currentProduct.product_name}
                        </h2>
                        <p className="text-sm text-muted-foreground">{currentProduct.brand}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-display text-lg font-bold text-primary">${currentProduct.price.toFixed(2)}</p>
                        <p className="text-xs text-muted-foreground">{CATEGORY_LABELS[currentProduct.category]}</p>
                      </div>
                    </div>

                    {currentProduct.short_description ? (
                      <p className="text-sm text-muted-foreground">{currentProduct.short_description}</p>
                    ) : null}

                    {currentProduct.ingredient_highlights && currentProduct.ingredient_highlights.length > 0 ? (
                      <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Key Ingredients</p>
                        <div className="flex flex-wrap gap-2">
                          {currentProduct.ingredient_highlights.map((ingredient) => (
                            <span key={ingredient} className="rounded-lg bg-secondary/50 px-2 py-1 text-xs">
                              {ingredient}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {currentProduct.skin_types_supported && currentProduct.skin_types_supported.length > 0 ? (
                      <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Skin Type Suitability</p>
                        <div className="flex flex-wrap gap-2">
                          {currentProduct.skin_types_supported.map((skinType) => (
                            <span key={skinType} className="rounded-lg bg-muted px-2 py-1 text-xs">
                              {skinType.replace(/_/g, " ")}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </motion.div>
              )}

              {step === "questionnaire" && reaction && (
                <motion.div
                  key="questionnaire"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="rounded-3xl border border-border bg-card p-5 shadow-lg"
                >
                  <h3 className="mb-2 font-display text-lg font-bold text-foreground">
                    Why did you {reaction === "like" ? "like" : "dislike"} this product?
                  </h3>
                  <p className="mb-4 text-sm text-muted-foreground">Select one or more options.</p>

                  <div className="mb-4 flex flex-wrap gap-2">
                    {availableReasons.map((reason) => (
                      <button
                        key={reason}
                        onClick={() => toggleReason(reason)}
                        className={`rounded-xl px-3 py-2 text-xs font-medium transition-all ${
                          selectedReasons.includes(reason)
                            ? "bg-primary text-primary-foreground"
                            : "border border-border bg-card text-foreground hover:bg-muted"
                        }`}
                      >
                        {reason}
                      </button>
                    ))}
                  </div>

                  <textarea
                    value={freeText}
                    onChange={(event) => setFreeText(event.target.value)}
                    placeholder="Other details (optional)"
                    className="mb-4 h-20 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
                  />

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => void handleQuestionnaireSubmit(false)}
                      className="flex-1 rounded-xl bg-primary px-4 py-3 text-sm font-medium text-primary-foreground"
                    >
                      Submit & Next
                    </button>
                    <button
                      onClick={() => void handleQuestionnaireSubmit(true)}
                      className="rounded-xl border border-border px-4 py-3 text-sm font-medium text-foreground"
                    >
                      Skip
                    </button>
                  </div>
                </motion.div>
              )}

              {step === "submitting" && (
                <motion.div
                  key="submitting"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex min-h-[200px] items-center justify-center"
                >
                  <Loader2 className="h-7 w-7 animate-spin text-primary" />
                </motion.div>
              )}
            </AnimatePresence>

            {step === "swipe" && currentProduct && (
              <div className="mt-6 flex items-center justify-center gap-4">
                <button
                  onClick={() => void handleSwipe("dislike")}
                  className="flex h-14 w-14 items-center justify-center rounded-full border border-border bg-card"
                  title="Dislike"
                >
                  <ThumbsDown className="h-5 w-5 text-destructive" />
                </button>
                <button
                  onClick={() => void handleSwipe("like")}
                  className="flex h-14 w-14 items-center justify-center rounded-full border border-border bg-card"
                  title="Like"
                >
                  <ThumbsUp className="h-5 w-5 text-success" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default Swiping;
