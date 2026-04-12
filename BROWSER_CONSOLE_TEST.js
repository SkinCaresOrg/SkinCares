#!/usr/bin/env node
/**
 * Browser Console Testing Guide for SkinCares API Response
 * 
 * Run this in your browser's developer console (F12 or Cmd+Option+I)
 * to verify the API response format.
 */

// Test 1: Verify API is accessible
console.log('%c🔍 SkinCares API Response Verification', 'color: #007AFF; font-size: 16px; font-weight: bold');
console.log('='.repeat(80));

// Test 2: Fetch products and verify response format
async function verifyApiResponse() {
  try {
    console.log('\n1️⃣ Fetching products from API...');
    const response = await fetch('/api/products?page=1&limit=5');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    console.log('✅ Response received successfully');
    console.log('Status:', response.status);
    console.log('Response keys:', Object.keys(data));
    
    // Test 3: Verify response structure
    console.log('\n2️⃣ Verifying response structure:');
    const requiredKeys = ['items', 'products', 'total', 'hasMore', 'page'];
    const missingKeys = requiredKeys.filter(key => !(key in data));
    
    if (missingKeys.length === 0) {
      console.log('✅ All required keys present');
    } else {
      console.error('❌ Missing keys:', missingKeys);
    }
    
    // Test 4: Verify items and products
    console.log('\n3️⃣ Verifying items and products:');
    console.log(`  - items count: ${data.items?.length ?? 0}`);
    console.log(`  - products count: ${data.products?.length ?? 0}`);
    console.log(`  - Both arrays equal: ${JSON.stringify(data.items) === JSON.stringify(data.products)}`);
    console.log(`  - total: ${data.total}`);
    console.log(`  - hasMore: ${data.hasMore}`);
    console.log(`  - page: ${data.page}`);
    
    // Test 5: Verify first product structure
    if (data.items && data.items.length > 0) {
      console.log('\n4️⃣ First product structure:');
      const firstProduct = data.items[0];
      console.log('Product object:', firstProduct);
      
      const requiredProductFields = [
        'product_id',
        'product_name',
        'brand',
        'category',
        'price',
        'image_url'
      ];
      
      const missingProductFields = requiredProductFields.filter(
        field => !(field in firstProduct)
      );
      
      if (missingProductFields.length === 0) {
        console.log('✅ All required product fields present');
      } else {
        console.error('❌ Missing product fields:', missingProductFields);
      }
      
      // Verify field types
      console.log('\n5️⃣ Field type verification:');
      console.log(`  - product_id: ${typeof firstProduct.product_id} (expected: number)`);
      console.log(`  - product_name: ${typeof firstProduct.product_name} (expected: string)`);
      console.log(`  - brand: ${typeof firstProduct.brand} (expected: string)`);
      console.log(`  - category: ${typeof firstProduct.category} (expected: string)`);
      console.log(`  - price: ${typeof firstProduct.price} (expected: number)`);
      console.log(`  - image_url: ${typeof firstProduct.image_url} (expected: string)`);
    }
    
    console.log('\n' + '='.repeat(80));
    console.log(
      '%c✅ API Response Format Verification Complete',
      'color: #34C759; font-size: 14px; font-weight: bold'
    );
    console.log('='.repeat(80));
    
    // Return data for further inspection
    console.log('\n💡 Tips:');
    console.log('- To inspect the full response: copy to clipboard with: copy(data)');
    console.log('- To see all products: use: console.table(data.items)');
    console.log('- To check individual product: use: data.items[0]');
    
    return data;
    
  } catch (error) {
    console.error('%c❌ Error during verification:', 'color: #FF3B30; font-weight: bold');
    console.error('Error:', error.message);
    console.error('Stack:', error.stack);
    
    // Provide troubleshooting steps
    console.log('\n🔧 Troubleshooting:');
    console.log('1. Check if API is running: verify it\'s accessible at http://localhost:8000');
    console.log('2. Check Network tab in Dev Tools for failed requests');
    console.log('3. Look for CORS errors in console');
    console.log('4. Verify API base URL in frontend/src/lib/api.ts');
    
    return null;
  }
}

// Run the verification
const result = await verifyApiResponse();

// Export result for inspection
if (result) {
  window.apiTestResult = result;
  console.log('\n💾 Result saved to: window.apiTestResult');
}
