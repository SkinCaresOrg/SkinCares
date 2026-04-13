# SkinCares API Contract (Frontend/Backend)

This contract is the stable integration surface for the SkinCares frontend and backend.

## Base URL

- Local base URL: `http://localhost:8000`
- API prefix: `/api`

All routes: `http://localhost:8000/api/...`

## Shared enums

### Categories
- `cleanser`
- `moisturizer`
- `sunscreen`
- `treatment`
- `face_mask`
- `eye_cream`

### Reactions
- `like`
- `dislike`
- `irritation`

`havent_tried` is not used as a reaction.

For feedback:
- `has_tried: true | false`
- if `has_tried=false`, no reaction is required
- if `has_tried=true`, reaction must be `like | dislike | irritation`

### Sort values
- `price_asc`
- `price_desc`

## Onboarding/profile values

### `skin_type`
- `normal`
- `dry`
- `oily`
- `combination`
- `sensitive`
- `not_sure`

### `sensitivity_level`
- `very_sensitive`
- `somewhat_sensitive`
- `rarely_sensitive`
- `not_sensitive`
- `not_sure`

### `price_range`
- `budget`
- `affordable`
- `mid_range`
- `premium`
- `no_preference`

### `routine_size`
- `minimal`
- `basic`
- `moderate`
- `extensive`

### `ingredient_exclusions`
- `fragrance`
- `alcohol`
- `essential_oils`
- `sulfates`
- `parabens`

### `concerns`
- `acne`
- `dryness`
- `oiliness`
- `redness`
- `dark_spots`
- `fine_lines`
- `dullness`
- `large_pores`
- `maintenance`

### `product_interests`
- `cleanser`
- `moisturizer`
- `sunscreen`
- `treatment`
- `face_mask`
- `eye_cream`

## Endpoints

### `POST /api/onboarding`

Request body:

```json
{
  "skin_type": "oily",
  "concerns": ["acne", "dark_spots"],
  "sensitivity_level": "very_sensitive",
  "ingredient_exclusions": ["fragrance", "alcohol"],
  "price_range": "affordable",
  "routine_size": "basic",
  "product_interests": ["cleanser", "treatment", "sunscreen"]
}
```

Response:

```json
{
  "user_id": "user_123",
  "profile": {
    "skin_type": "oily",
    "concerns": ["acne", "dark_spots"],
    "sensitivity_level": "very_sensitive",
    "ingredient_exclusions": ["fragrance", "alcohol"],
    "price_range": "affordable",
    "routine_size": "basic",
    "product_interests": ["cleanser", "treatment", "sunscreen"]
  }
}
```

### `GET /api/products`

Optional query params:
- `category`
- `sort`
- `search`
- `min_price`
- `max_price`
- `limit`
- `offset`

Example:
`/api/products?category=moisturizer&sort=price_asc&search=cera&min_price=10&max_price=40`

Response shape:

```json
{
  "products": [
    {
      "product_id": 101,
      "product_name": "Daily Barrier Cream",
      "brand": "CeraVe",
      "category": "moisturizer",
      "price": 18.99,
      "image_url": "/images/101.jpg",
      "short_description": "Barrier-supporting daily moisturizer",
      "rating_count": 124,
      "wishlist_supported": true
    }
  ],
  "total": 1
}
```

### `GET /api/products/{product_id}`

Response shape:

```json
{
  "product_id": 101,
  "product_name": "Daily Barrier Cream",
  "brand": "CeraVe",
  "category": "moisturizer",
  "price": 18.99,
  "image_url": "/images/101.jpg",
  "short_description": "Barrier-supporting daily moisturizer",
  "ingredients": ["ceramides", "glycerin", "cholesterol"],
  "ingredient_highlights": ["ceramides", "glycerin"],
  "concerns_targeted": ["dryness", "redness"],
  "skin_types_supported": ["dry", "sensitive", "combination"]
}
```

### `GET /api/recommendations/{user_id}`

Optional query params:
- `category`
- `limit`

Response shape:

```json
{
  "products": [
    {
      "product_id": 220,
      "product_name": "Invisible Daily SPF 50",
      "brand": "Beauty of Joseon",
      "category": "sunscreen",
      "price": 17.5,
      "image_url": "/images/220.jpg",
      "recommendation_score": 0.91,
      "explanation": "Matches oily, acne-prone, fragrance-avoidant profile"
    }
  ]
}
```

### `GET /api/dupes/{product_id}`

Response shape:

```json
{
  "source_product_id": 220,
  "dupes": [
    {
      "product_id": 305,
      "product_name": "Light Gel SPF 50",
      "brand": "Isntree",
      "category": "sunscreen",
      "price": 15.0,
      "image_url": "/images/305.jpg",
      "dupe_score": 0.88,
      "explanation": "Similar texture and use case at a comparable/lower price"
    }
  ]
}
```

### `POST /api/feedback`

Case 1 (`has_tried=false`):

```json
{
  "user_id": "user_123",
  "product_id": 220,
  "has_tried": false
}
```

Case 2 (`has_tried=true`):

```json
{
  "user_id": "user_123",
  "product_id": 220,
  "has_tried": true,
  "reaction": "dislike",
  "reason_tags": ["felt_greasy", "broke_me_out"],
  "free_text": "It felt heavy and made my skin greasy."
}
```

Response:

```json
{
  "success": true,
  "message": "Feedback recorded"
}
```

## Frontend assumptions

- Catalog page: all products + filters/search/sort
- Recommendations page: personalized by `user_id`
- Product modal can fetch details and dupes
- `product_id` is stable across endpoints
- Numeric values (`price`, `dupe_score`, etc.) return as numbers
- Arrays return as empty arrays, not `null`
- Enum values remain stable and exact

## Local dev notes

- Enable CORS for local frontend origins
- Keep field names stable across all endpoints
- Keep product object shape consistent where possible
