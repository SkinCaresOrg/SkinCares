import { DupeProduct, CATEGORY_LABELS, formatPrice, Category } from "@/lib/types";

interface DupeListProps {
  dupes: DupeProduct[];
  loading: boolean;
}

const CATEGORY_GRADIENTS: Record<Category, string> = {
  cleanser: "from-sky-100 to-blue-50",
  moisturizer: "from-emerald-100 to-teal-50",
  sunscreen: "from-amber-100 to-yellow-50",
  treatment: "from-violet-100 to-purple-50",
  face_mask: "from-rose-100 to-pink-50",
  eye_cream: "from-indigo-100 to-blue-50",
};

const DupeList = ({ dupes, loading }: DupeListProps) => {
  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {[1, 2].map((i) => (
          <div key={i} className="h-28 animate-pulse rounded-2xl bg-muted" />
        ))}
      </div>
    );
  }

  if (dupes.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">No dupes found for this product.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {dupes.map((dupe) => (
        <div key={dupe.product_id} className="flex items-center gap-4 rounded-2xl border border-border bg-muted/30 p-3">
          <div className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${CATEGORY_GRADIENTS[dupe.category]} overflow-hidden`}>
            {dupe.image_url && dupe.image_url.trim().length > 0 ? (
              <img
                src={dupe.image_url}
                alt={dupe.product_name}
                className="h-full w-full object-cover object-center"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
            ) : (
              <span className="text-[10px] font-bold text-foreground/10">{CATEGORY_LABELS[dupe.category]}</span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-display text-sm font-semibold text-foreground">{dupe.product_name}</p>
            <p className="text-xs text-muted-foreground">{dupe.brand}</p>
            <p className="mt-1 text-xs italic text-primary/70">{dupe.explanation}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className="font-display text-sm font-bold text-primary">{formatPrice(dupe.price)}</p>
            <p className="mt-0.5 rounded-lg bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
              {Math.round(dupe.dupe_score * 100)}% match
            </p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default DupeList;
