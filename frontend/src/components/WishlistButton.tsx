import { Heart } from "lucide-react";
import { useState, useEffect } from "react";
import { isInWishlist, toggleWishlist } from "@/lib/wishlist";
import { cn } from "@/lib/utils";

interface WishlistButtonProps {
  productId: number;
  className?: string;
}

const WishlistButton = ({ productId, className }: WishlistButtonProps) => {
  const [wishlisted, setWishlisted] = useState(false);

  useEffect(() => {
    setWishlisted(isInWishlist(productId));
  }, [productId]);

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    toggleWishlist(productId);
    setWishlisted(!wishlisted);
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
