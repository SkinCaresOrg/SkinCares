import { useState, useEffect } from "react";
import { X, Sparkles } from "lucide-react";
import { Product, ProductDetail, CATEGORY_LABELS, formatPrice, Category } from "@/lib/types";
import { getProductDetail, getDupes } from "@/lib/api";
import { DupeProduct } from "@/lib/types";
import WishlistButton from "./WishlistButton";
import FeedbackPanel from "./FeedbackPanel";
import DupeList from "./DupeList";
import { motion, AnimatePresence } from "framer-motion";

interface ProductModalProps {
  product: Product | null;
  onClose: () => void;
}

const CATEGORY_GRADIENTS: Record<Category, string> = {
  cleanser: "from-sky-100 to-blue-50",
  moisturizer: "from-emerald-100 to-teal-50",
  sunscreen: "from-amber-100 to-yellow-50",
  treatment: "from-violet-100 to-purple-50",
  face_mask: "from-rose-100 to-pink-50",
  eye_cream: "from-indigo-100 to-blue-50",
};

const ProductModal = ({ product, onClose }: ProductModalProps) => {
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [showDupes, setShowDupes] = useState(false);
  const [dupes, setDupes] = useState<DupeProduct[]>([]);
  const [dupesLoading, setDupesLoading] = useState(false);

  useEffect(() => {
    if (!product) return;
    setLoading(true);
    setShowDupes(false);
    setDupes([]);
    getProductDetail(product.product_id).then((d) => {
      setDetail(d);
      setLoading(false);
    });
  }, [product]);

  const handleFindDupes = async () => {
    if (!product) return;
    setShowDupes(true);
    setDupesLoading(true);
    const res = await getDupes(product.product_id);
    setDupes(res.dupes);
    setDupesLoading(false);
  };

  if (!product) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-end justify-center bg-foreground/20 backdrop-blur-sm sm:items-center sm:p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-t-3xl bg-card sm:rounded-3xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header image */}
          <div className={`relative flex h-52 items-center justify-center bg-gradient-to-br ${CATEGORY_GRADIENTS[product.category]} overflow-hidden`}>
            {product.image_url && product.image_url.trim().length > 0 ? (
              <img
                src={product.image_url}
                alt={product.product_name}
                className="h-full w-full object-cover object-center"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
            ) : (
              <span className="font-display text-5xl font-bold text-foreground/10">{CATEGORY_LABELS[product.category]}</span>
            )}
            <button onClick={onClose} className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-xl bg-card/80 text-foreground backdrop-blur-sm transition-colors hover:bg-card">
              <X className="h-4 w-4" />
            </button>
            <div className="absolute left-4 top-4">
              <WishlistButton productId={product.product_id} />
            </div>
          </div>

          <div className="flex flex-col gap-5 p-6">
            {/* Title */}
            <div>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-display text-xl font-bold text-foreground">{product.product_name}</h2>
                  <p className="text-sm text-muted-foreground">{product.brand}</p>
                </div>
                <span className="whitespace-nowrap font-display text-xl font-bold text-primary">{formatPrice(product.price)}</span>
              </div>
              <span className="mt-2 inline-flex rounded-lg bg-secondary/50 px-2.5 py-1 text-xs font-medium text-secondary-foreground">
                {CATEGORY_LABELS[product.category]}
              </span>
            </div>

            {loading ? (
              <div className="flex flex-col gap-3">
                {[1, 2, 3].map((i) => <div key={i} className="h-6 animate-pulse rounded-lg bg-muted" />)}
              </div>
            ) : detail && (
              <>
                {/* Ingredients */}
                {detail.ingredients.length > 0 && (
                  <div>
                    <h3 className="mb-2 font-display text-xs font-semibold uppercase tracking-wider text-muted-foreground">Ingredients</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {detail.ingredients.map((ing) => (
                        <span
                          key={ing}
                          className={`rounded-lg px-2.5 py-1 text-xs ${
                            detail.ingredient_highlights?.includes(ing)
                              ? "bg-primary/10 font-medium text-primary"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {ing}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Concerns */}
                {detail.concerns_targeted && detail.concerns_targeted.length > 0 && (
                  <div>
                    <h3 className="mb-2 font-display text-xs font-semibold uppercase tracking-wider text-muted-foreground">Targets</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {detail.concerns_targeted.map((c) => (
                        <span key={c} className="rounded-lg bg-success/10 px-2.5 py-1 text-xs font-medium text-success">{c}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Skin types */}
                {detail.skin_types_supported && detail.skin_types_supported.length > 0 && (
                  <div>
                    <h3 className="mb-2 font-display text-xs font-semibold uppercase tracking-wider text-muted-foreground">Good for</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {detail.skin_types_supported.map((st) => (
                        <span key={st} className="rounded-lg bg-secondary/50 px-2.5 py-1 text-xs font-medium text-secondary-foreground capitalize">{st} skin</span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Find Dupes */}
            {!showDupes ? (
              <button
                onClick={handleFindDupes}
                className="flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition-all hover:bg-muted"
              >
                <Sparkles className="h-4 w-4 text-primary" />
                Find Dupes
              </button>
            ) : (
              <div>
                <h3 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-muted-foreground">Similar Products</h3>
                <DupeList dupes={dupes} loading={dupesLoading} />
              </div>
            )}

            {/* Feedback */}
            <FeedbackPanel productId={product.product_id} category={product.category} />
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default ProductModal;
