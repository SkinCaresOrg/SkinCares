import { useState, useEffect, useRef, useCallback } from "react";
import { getProducts } from "@/lib/api";
import { Product, Category, SortValue } from "@/lib/types";
import ProductCard from "@/components/ProductCard";
import ProductModal from "@/components/ProductModal";
import FilterBar from "@/components/FilterBar";
import Navigation from "@/components/Navigation";
import { Package } from "lucide-react";

const CATALOG_PAGE_SIZE = 20;
const SCROLL_TRIGGER_PX = 300;

const Catalog = () => {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [sort, setSort] = useState<SortValue | "">("");
  const [skinType, setSkinType] = useState("");
  const [concern, setConcern] = useState("");
  const [brand, setBrand] = useState("");
  const [ingredient, setIngredient] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const isFetching = useRef(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);

    return () => {
      clearTimeout(timer);
    };
  }, [search]);

  const fetchPage = useCallback(
    async (targetPage: number, replace: boolean) => {
      if (isFetching.current) {
        return;
      }
      if (!replace && (!hasMore || loading)) {
        return;
      }

      isFetching.current = true;
      setLoading(true);

      try {
        const res = await getProducts({
          category: category || undefined,
          sort: sort || undefined,
          search: debouncedSearch || undefined,
          skin_type: skinType || undefined,
          concern: concern || undefined,
          brand: brand || undefined,
          ingredient: ingredient || undefined,
          min_price: minPrice ? Number(minPrice) : undefined,
          max_price: maxPrice ? Number(maxPrice) : undefined,
          page: targetPage,
          limit: CATALOG_PAGE_SIZE,
        });

        setProducts((prev) => (replace ? res.items : [...prev, ...res.items]));
        setHasMore(res.hasMore);
        setPage(res.page);
      } finally {
        setLoading(false);
        setInitialLoading(false);
        isFetching.current = false;
      }
    },
    [
      category,
      sort,
      debouncedSearch,
      skinType,
      concern,
      brand,
      ingredient,
      minPrice,
      maxPrice,
      hasMore,
      loading,
    ]
  );

  useEffect(() => {
    setProducts([]);
    setPage(1);
    setHasMore(true);
    setInitialLoading(true);
    void fetchPage(1, true);
  }, [
    debouncedSearch,
    category,
    sort,
    skinType,
    concern,
    brand,
    ingredient,
    minPrice,
    maxPrice,
    fetchPage,
  ]);

  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const viewportHeight = window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight;
      const isNearBottom = scrollTop + viewportHeight >= documentHeight - SCROLL_TRIGGER_PX;

      if (isNearBottom && hasMore && !loading && !isFetching.current) {
        void fetchPage(page + 1, false);
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, [fetchPage, hasMore, loading, page]);

  const productList = products;

  return (
    <div className="min-h-screen">
      <Navigation />
      <main className="container py-8">
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold text-foreground">Product Catalog</h1>
          <p className="mt-1 text-sm text-muted-foreground">Discover products curated for your skin</p>
        </div>

        <FilterBar
          search={search}
          onSearchChange={setSearch}
          selectedCategory={category}
          onCategoryChange={setCategory}
          sort={sort}
          onSortChange={setSort}
          skinType={skinType}
          onSkinTypeChange={setSkinType}
          concern={concern}
          onConcernChange={setConcern}
          brand={brand}
          onBrandChange={setBrand}
          ingredient={ingredient}
          onIngredientChange={setIngredient}
          minPrice={minPrice}
          maxPrice={maxPrice}
          onMinPriceChange={setMinPrice}
          onMaxPriceChange={setMaxPrice}
        />

        <div className="mt-8">
          {initialLoading ? (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="h-72 animate-pulse rounded-2xl bg-muted" />
              ))}
            </div>
          ) : productList.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <Package className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="mt-4 font-display text-lg font-semibold text-foreground">No products found</p>
              <p className="mt-1 text-sm text-muted-foreground">Try adjusting your search or filters</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {productList.map((product) => (
                <ProductCard key={product.product_id} product={product} onClick={setSelectedProduct} />
              ))}
            </div>
          )}

          {loading && !initialLoading && (
            <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <div key={`loading-more-${i}`} className="h-72 animate-pulse rounded-2xl bg-muted" />
              ))}
            </div>
          )}

          {!hasMore && productList.length > 0 && !loading && (
            <p className="mt-6 text-center text-sm text-muted-foreground">You have seen all products.</p>
          )}

          {loading && !initialLoading && (
            <p className="mt-4 text-xs text-muted-foreground">Updating products…</p>
          )}
        </div>
      </main>

      <ProductModal product={selectedProduct} onClose={() => setSelectedProduct(null)} />
    </div>
  );
};

export default Catalog;
