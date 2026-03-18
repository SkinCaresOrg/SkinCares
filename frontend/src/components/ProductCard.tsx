import { Product, CATEGORY_LABELS, formatPrice, Category } from "@/lib/types";
import WishlistButton from "./WishlistButton";

interface ProductCardProps {
  product: Product;
  onClick: (product: Product) => void;
  explanation?: string;
  score?: number;
  scoreLabel?: string;
}

const CATEGORY_GRADIENTS: Record<Category, string> = {
  cleanser: "from-sky-100 to-blue-50",
  moisturizer: "from-emerald-100 to-teal-50",
  sunscreen: "from-amber-100 to-yellow-50",
  treatment: "from-violet-100 to-purple-50",
  face_mask: "from-rose-100 to-pink-50",
  eye_cream: "from-indigo-100 to-blue-50",
};

const ProductCard = ({ product, onClick, explanation, score, scoreLabel }: ProductCardProps) => {
  return (
    <button
      onClick={() => onClick(product)}
      className="group flex w-full flex-col overflow-hidden rounded-2xl border border-border bg-card text-left shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary/30"
    >
      <div className={`relative flex h-44 items-center justify-center bg-gradient-to-br ${CATEGORY_GRADIENTS[product.category]}`}>
        <span className="font-display text-3xl font-bold text-foreground/10">
          {CATEGORY_LABELS[product.category]}
        </span>
        <div className="absolute right-3 top-3">
          <WishlistButton productId={product.product_id} />
        </div>
        {score !== undefined && (
          <div className="absolute left-3 top-3 rounded-xl bg-card/90 px-2.5 py-1 text-xs font-semibold text-primary backdrop-blur-sm">
            {scoreLabel || "Score"}: {Math.round(score * 100)}%
          </div>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="truncate font-display text-sm font-semibold text-foreground">{product.product_name}</p>
            <p className="text-xs text-muted-foreground">{product.brand}</p>
          </div>
          <span className="whitespace-nowrap font-display text-sm font-bold text-primary">
            {formatPrice(product.price)}
          </span>
        </div>
        <span className="inline-flex w-fit rounded-lg bg-secondary/50 px-2 py-0.5 text-[11px] font-medium text-secondary-foreground">
          {CATEGORY_LABELS[product.category]}
        </span>
        {product.short_description && (
          <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">{product.short_description}</p>
        )}
        {explanation && (
          <p className="mt-auto line-clamp-2 text-xs italic leading-relaxed text-primary/80">{explanation}</p>
        )}
      </div>
    </button>
  );
};

export default ProductCard;
