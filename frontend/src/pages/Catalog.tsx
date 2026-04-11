import { useState, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getProducts } from "@/lib/api";
import { Product, Category, SortValue } from "@/lib/types";
import ProductCard from "@/components/ProductCard";
import ProductModal from "@/components/ProductModal";
import FilterBar from "@/components/FilterBar";
import Navigation from "@/components/Navigation";
import { Package } from "lucide-react";

const CATALOG_PAGE_SIZE = 500;

const Catalog = () => {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [sort, setSort] = useState<SortValue | "">("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);

    return () => {
      clearTimeout(timer);
    };
  }, [search]);

  const {
    data: products,
    isLoading,
    isFetching,
  } = useQuery({
    queryKey: ["catalog-products", debouncedSearch, category, sort],
    queryFn: async () => {
      const merged: Product[] = [];
      let offset = 0;
      let total = Number.POSITIVE_INFINITY;

      while (offset < total) {
        const res = await getProducts({
          category: category || undefined,
          sort: sort || undefined,
          search: debouncedSearch || undefined,
          limit: CATALOG_PAGE_SIZE,
          offset,
        });

        merged.push(...res.products);
        total = res.total;
        offset += res.products.length;

        if (res.products.length === 0) {
          break;
        }
      }

      return merged;
    },
    staleTime: 2 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });

  const productList = products ?? [];

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
        />

        <div className="mt-8">
          {isLoading ? (
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

          {isFetching && !isLoading && (
            <p className="mt-4 text-xs text-muted-foreground">Updating products…</p>
          )}
        </div>
      </main>

      <ProductModal product={selectedProduct} onClose={() => setSelectedProduct(null)} />
    </div>
  );
};

export default Catalog;
