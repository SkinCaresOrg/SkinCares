import { Search, ChevronDown } from "lucide-react";
import { Category, CATEGORIES, CATEGORY_LABELS, SortValue } from "@/lib/types";

interface FilterBarProps {
  search: string;
  onSearchChange: (v: string) => void;
  selectedCategory: Category | null;
  onCategoryChange: (c: Category | null) => void;
  sort: SortValue | "";
  onSortChange: (s: SortValue | "") => void;
}

const FilterBar = ({ search, onSearchChange, selectedCategory, onCategoryChange, sort, onSortChange }: FilterBarProps) => {
  return (
    <div className="flex flex-col gap-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search products or brands..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="h-12 w-full rounded-2xl border border-border bg-card pl-11 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10 transition-all"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Category chips */}
        <button
          onClick={() => onCategoryChange(null)}
          className={`rounded-xl px-3.5 py-2 text-xs font-medium transition-all ${
            !selectedCategory
              ? "bg-primary text-primary-foreground shadow-sm"
              : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
          }`}
        >
          All
        </button>
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => onCategoryChange(cat === selectedCategory ? null : cat)}
            className={`rounded-xl px-3.5 py-2 text-xs font-medium transition-all ${
              selectedCategory === cat
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            }`}
          >
            {CATEGORY_LABELS[cat]}
          </button>
        ))}

        {/* Sort */}
        <div className="relative ml-auto">
          <select
            value={sort}
            onChange={(e) => onSortChange(e.target.value)}
            className="appearance-none rounded-xl border border-border bg-card px-3.5 py-2 pr-8 text-xs font-medium text-foreground focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10"
          >
            <option value="">Sort by</option>
            <option value="price_asc">Price: Low → High</option>
            <option value="price_desc">Price: High → Low</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        </div>
      </div>
    </div>
  );
};

export default FilterBar;
