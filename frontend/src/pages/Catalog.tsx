import { useState, useEffect, useMemo } from "react";
import { getProducts } from "@/lib/api";
import { Product, Category, SortValue } from "@/lib/types";
import ProductCard from "@/components/ProductCard";
import ProductModal from "@/components/ProductModal";
import FilterBar from "@/components/FilterBar";
import Navigation from "@/components/Navigation";
import { Package } from "lucide-react";

const Catalog = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [sort, setSort] = useState<SortValue | "">("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      getProducts({
        category: category || undefined,
        sort: sort || undefined,
        search: search || undefined,
      }).then((res) => {
        setProducts(res.products);
        setLoading(false);
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [search, category, sort]);

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
          {loading ? (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="h-72 animate-pulse rounded-2xl bg-muted" />
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <Package className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="mt-4 font-display text-lg font-semibold text-foreground">No products found</p>
              <p className="mt-1 text-sm text-muted-foreground">Try adjusting your search or filters</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {products.map((product) => (
                <ProductCard key={product.product_id} product={product} onClick={setSelectedProduct} />
              ))}
            </div>
          )}
        </div>
      </main>

      <ProductModal product={selectedProduct} onClose={() => setSelectedProduct(null)} />
    </div>
  );
};

export default Catalog;
