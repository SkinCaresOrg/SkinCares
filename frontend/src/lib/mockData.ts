import { Product, ProductDetail, RecommendedProduct, DupeProduct } from "./types";

export const MOCK_PRODUCTS: Product[] = [
  { product_id: 101, product_name: "Daily Barrier Cream", brand: "CeraVe", category: "moisturizer", price: 18.99, image_url: "", short_description: "Barrier-supporting daily moisturizer", rating_count: 124 },
  { product_id: 102, product_name: "Hydrating Facial Cleanser", brand: "CeraVe", category: "cleanser", price: 15.99, image_url: "", short_description: "Gentle hydrating cleanser for daily use", rating_count: 231 },
  { product_id: 103, product_name: "Relief Sun SPF50+", brand: "Beauty of Joseon", category: "sunscreen", price: 17.50, image_url: "", short_description: "Lightweight rice probiotic sunscreen", rating_count: 892 },
  { product_id: 104, product_name: "Snail Mucin Essence", brand: "COSRX", category: "treatment", price: 21.00, image_url: "", short_description: "Hydrating snail secretion filtrate", rating_count: 1450 },
  { product_id: 105, product_name: "Green Tea Seed Cream", brand: "Innisfree", category: "moisturizer", price: 24.00, image_url: "", short_description: "Antioxidant-rich green tea moisturizer", rating_count: 567 },
  { product_id: 106, product_name: "Low pH Good Morning Cleanser", brand: "COSRX", category: "cleanser", price: 12.00, image_url: "", short_description: "Low pH gentle morning cleanser", rating_count: 2100 },
  { product_id: 107, product_name: "Honey Glow Mask", brand: "I'm From", category: "face_mask", price: 22.00, image_url: "", short_description: "Nourishing honey wash-off mask", rating_count: 340 },
  { product_id: 108, product_name: "Retinol Eye Cream", brand: "CeraVe", category: "eye_cream", price: 19.99, image_url: "", short_description: "Gentle retinol eye cream for fine lines", rating_count: 89 },
  { product_id: 109, product_name: "BHA Blackhead Power Liquid", brand: "COSRX", category: "treatment", price: 25.00, image_url: "", short_description: "Salicylic acid exfoliant for blackheads", rating_count: 3200 },
  { product_id: 110, product_name: "Centella Unscented Serum", brand: "Purito", category: "treatment", price: 16.50, image_url: "", short_description: "Fragrance-free calming centella serum", rating_count: 780 },
  { product_id: 111, product_name: "Aqua Sun Gel SPF50", brand: "Missha", category: "sunscreen", price: 13.99, image_url: "", short_description: "Lightweight watery sunscreen gel", rating_count: 445 },
  { product_id: 112, product_name: "Rice Wash-Off Mask", brand: "Skinfood", category: "face_mask", price: 10.00, image_url: "", short_description: "Brightening rice bran wash-off mask", rating_count: 670 },
];

export const MOCK_PRODUCT_DETAIL: ProductDetail = {
  product_id: 101,
  product_name: "Daily Barrier Cream",
  brand: "CeraVe",
  category: "moisturizer",
  price: 18.99,
  image_url: "",
  short_description: "Barrier-supporting daily moisturizer",
  ingredients: ["ceramides", "glycerin", "cholesterol", "hyaluronic acid", "niacinamide", "phytosphingosine"],
  ingredient_highlights: ["ceramides", "glycerin", "niacinamide"],
  concerns_targeted: ["dryness", "redness", "sensitivity_level"],
  skin_types_supported: ["dry", "sensitive", "combination"],
};

export const MOCK_RECOMMENDATIONS: RecommendedProduct[] = [
  { product_id: 103, product_name: "Relief Sun SPF50+", brand: "Beauty of Joseon", category: "sunscreen", price: 17.50, image_url: "", recommendation_score: 0.95, explanation: "Lightweight formula ideal for oily, acne-prone skin" },
  { product_id: 110, product_name: "Centella Unscented Serum", brand: "Purito", category: "treatment", price: 16.50, image_url: "", recommendation_score: 0.91, explanation: "Fragrance-free, calming — great for sensitive skin" },
  { product_id: 106, product_name: "Low pH Good Morning Cleanser", brand: "COSRX", category: "cleanser", price: 12.00, image_url: "", recommendation_score: 0.89, explanation: "Gentle, low pH cleanser that won't strip your moisture barrier" },
  { product_id: 101, product_name: "Daily Barrier Cream", brand: "CeraVe", category: "moisturizer", price: 18.99, image_url: "", recommendation_score: 0.87, explanation: "Ceramide-rich moisturizer for barrier repair" },
  { product_id: 112, product_name: "Rice Wash-Off Mask", brand: "Skinfood", category: "face_mask", price: 10.00, image_url: "", recommendation_score: 0.82, explanation: "Gentle brightening mask at a budget-friendly price" },
  { product_id: 108, product_name: "Retinol Eye Cream", brand: "CeraVe", category: "eye_cream", price: 19.99, image_url: "", recommendation_score: 0.78, explanation: "Gentle retinol for under-eye fine lines and dark circles" },
];

export const MOCK_DUPES: DupeProduct[] = [
  { product_id: 305, product_name: "Light Gel SPF 50", brand: "Isntree", category: "sunscreen", price: 15.00, image_url: "", dupe_score: 0.88, explanation: "Similar lightweight texture at a lower price point" },
  { product_id: 306, product_name: "Watery Sun Essence", brand: "Biore", category: "sunscreen", price: 12.50, image_url: "", dupe_score: 0.82, explanation: "Budget-friendly alternative with similar feel and protection" },
];
