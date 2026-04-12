import { Heart } from "lucide-react";
import { useState, useEffect } from "react";
import { addToWishlist, getWishlistItems, removeFromWishlist } from "@/lib/api";
import { cn } from "@/lib/utils";

interface WishlistButtonProps {
  productId: number;
  className?: string;
}

const WishlistButton = ({ productId, className }: WishlistButtonProps) => {
  const [wishlisted, setWishlisted] = useState(false);

  useEffect(() => {
    let mounted = true;
    getWishlistItems()
      .then((payload) => {
        if (!mounted) return;
        setWishlisted(payload.items.some((item) => item.product_id === productId));
      })
      .catch(() => {
        if (!mounted) return;
        setWishlisted(false);
      });

    return () => {
      mounted = false;
    };
  }, [productId]);

  const handleToggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const next = !wishlisted;
    setWishlisted(next);
    try {
      if (next) {
        await addToWishlist(productId);
      } else {
        await removeFromWishlist(productId);
      }
      window.dispatchEvent(new CustomEvent("skincares-wishlist-updated"));
    } catch {
      setWishlisted(!next);
    }
  };

  return (
    <button
      onClick={handleToggle}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-xl transition-all duration-200",
        wishlisted
          ? "bg-primary/10 text-primary hover:bg-primary/20"
          : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground",
        className
      )}
      aria-label={wishlisted ? "Remove from wishlist" : "Add to wishlist"}
    >
      <Heart className={cn("h-4 w-4 transition-all", wishlisted && "fill-current")} />
    </button>
  );
};

export default WishlistButton;
