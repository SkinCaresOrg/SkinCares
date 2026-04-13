#!/usr/bin/env python
"""Debug script to understand why likes aren't boosting products."""

import sys
sys.path.insert(0, '.')

from tests.test_recommendation_regression import _onboard_user, _get_recommendations, _rank_and_score
from fastapi.testclient import TestClient
from deployment.api import app

client = TestClient(app)
user_id = _onboard_user()

before = _get_recommendations(user_id)
print(f'Total recommendations: {len(before)}')
print('Top 15 products and scores:')
for i, p in enumerate(before[:15], 1):
    print(f'  {i:2d}. Product {p["product_id"]:5d}: {p["recommendation_score"]:.4f}')

target = before[9]
target_id = target['product_id']
before_rank, before_score = _rank_and_score(before, target_id)
print(f'\nTarget product (rank 10): ID={target_id}, rank={before_rank}, score={before_score:.4f}')

print('\nApplying 10 likes...')
for i in range(10):
    response = client.post(
        '/api/feedback',
        json={
            'user_id': user_id,
            'product_id': target_id,
            'has_tried': True,
            'reaction': 'like',
            'reason_tags': ['hydrating', 'non_irritating'],
            'free_text': 'Hydrating and gentle',
        },
    )
    print(f'  Like {i+1}: status={response.status_code}')

after = _get_recommendations(user_id)
print('\nAfter 10 likes - Top 15 products and scores:')
for i, p in enumerate(after[:15], 1):
    print(f'  {i:2d}. Product {p["product_id"]:5d}: {p["recommendation_score"]:.4f}')

after_rank, after_score = _rank_and_score(after, target_id)
print(f'\nTarget product after: rank={after_rank}, score={after_score:.4f}')
print(f'Score improvement: {after_score - before_score:.4f} (needed: +0.06)')
print(f'Rank improvement: {before_rank - after_rank} (needed: >=2)')
