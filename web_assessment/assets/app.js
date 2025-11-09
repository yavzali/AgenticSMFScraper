// Global state
let currentProducts = [];
let currentProductForModal = null;
let currentReviewType = '';

// Initialize the interface
document.addEventListener('DOMContentLoaded', function() {
    loadSystemStats();
    loadProducts();
    setReviewType(''); // Start with all products
});

// Set review type and update tab styling
function setReviewType(reviewType) {
    currentReviewType = reviewType;
    
    // Update tab styling
    document.getElementById('modestyReviewTab').style.opacity = reviewType === 'modesty_assessment' ? '1' : '0.7';
    document.getElementById('duplicateReviewTab').style.opacity = reviewType === 'duplicate_uncertain' ? '1' : '0.7';
    document.getElementById('allReviewTab').style.opacity = reviewType === '' ? '1' : '0.7';
    
    loadProducts();
}

// Load system stats
async function loadSystemStats() {
    // Stats are loaded with products for efficiency
}

// Load products from backend
async function loadProducts() {
    try {
        const retailer = document.getElementById('retailerFilter').value;
        const category = document.getElementById('categoryFilter').value;
        const confidence = document.getElementById('confidenceFilter').value;
        
        const params = new URLSearchParams({
            retailer: retailer,
            category: category,
            confidence: confidence,
            review_type: currentReviewType
        });
        
        const response = await fetch(`api/get_products.php?${params}`);
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        currentProducts = data.products;
        updateStats(data.stats);
        renderProducts(currentProducts);
        
    } catch (error) {
        console.error('Error loading products:', error);
        showToast('Error loading products: ' + error.message, 'error');
    }
}

function updateStats(stats) {
    document.getElementById('pendingCount').textContent = stats.total_pending || 0;
    document.getElementById('approvedCount').textContent = stats.approved_today || 0;
    document.getElementById('totalProcessed').textContent = stats.total_processed || 0;
    document.getElementById('lowConfidenceCount').textContent = stats.low_confidence || 0;
}

// Render products
function renderProducts(products) {
    const container = document.getElementById('products-container');
    
    if (!products || products.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No products found</h3>
                <p>No products match the current filters.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = products.map(product => generateProductCard(product)).join('');
}

// Generate product card HTML
function generateProductCard(product) {
    const reviewTypeBadge = getReviewTypeBadge(product.review_type);
    const confidenceClass = getConfidenceClass(product.confidence_score);
    const imagesHtml = generateImagesHtml(product.display_images || []);
    const matchesHtml = generatePotentialMatchesHtml(product.similarity_matches);
    const actionsHtml = generateActionsHtml(product.review_type, product.id);
    
    return `
        <div class="product-card" data-id="${product.id}">
            <div class="product-header">
                ${reviewTypeBadge}
                <span class="confidence-score ${confidenceClass}">
                    ${Math.round(product.confidence_score * 100)}%
                </span>
            </div>
            
            ${imagesHtml}
            
            <div class="product-details">
                <h3 class="product-title">${escapeHtml(product.title)}</h3>
                <div class="product-meta">
                    <span class="price-tag">$${product.price}</span>
                    <span class="retailer-badge">${escapeHtml(product.retailer)}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">Category:</span>
                    <span class="detail-value">${escapeHtml(product.category)}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">Source:</span>
                    <a href="${product.catalog_url}" target="_blank" class="detail-link" style="color: #667eea; text-decoration: none;">View Original</a>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">Discovered:</span>
                    <span class="detail-value">${new Date(product.discovered_date).toLocaleDateString()}</span>
                </div>
            </div>
            
            <!-- Product Type Classification Section -->
            <div class="classification-section" style="margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #667eea;">
                <h4 style="margin: 0 0 10px 0; color: #2c3e50; font-size: 0.95rem;">Product Classification</h4>
                
                <!-- Display extracted type info -->
                <div class="extracted-info" style="margin-bottom: 12px; padding: 8px; background: #e3f2fd; border-radius: 4px; font-size: 0.9rem;">
                    <strong>Extracted Type:</strong> 
                    <span style="color: #1976d2; font-weight: 600;">
                        ${product.clothing_type || 'unknown'}
                    </span>
                    ${product.clothing_type_source ? `<span style="color: #666; font-size: 0.85rem;"> (${product.clothing_type_source})</span>` : ''}
                </div>
                
                <!-- Product type selection -->
                <label for="clothing_type_${product.id}" style="display: block; font-weight: 600; margin-bottom: 6px; font-size: 0.9rem;">
                    Confirm Product Type: <span style="color: #e74c3c;">*</span>
                </label>
                <select 
                    name="clothing_type" 
                    id="clothing_type_${product.id}" 
                    class="clothing-type-select"
                    required
                    style="width: 100%; padding: 8px; font-size: 0.9rem; border: 2px solid #bdc3c7; border-radius: 4px; background: white;"
                >
                    ${generateClothingTypeOptions(product.clothing_type || '')}
                </select>
                <p style="margin-top: 6px; font-size: 0.8rem; color: #7f8c8d; font-style: italic;">
                    💡 Select "Dress Top" for long tops/tunics that can be worn as dresses
                </p>
            </div>
            
            ${matchesHtml}
            
            <div class="product-actions">
                ${actionsHtml}
            </div>
        </div>
    `;
}

function generateImagesHtml(images) {
    if (!images || images.length === 0) {
        return '<div style="padding: 20px; text-align: center; color: #999;">No images available</div>';
    }
    
    return `
        <div class="product-images">
            ${images.map(url => `<img src="${url}" class="product-image" alt="Product image">`).join('')}
        </div>
    `;
}

function generatePotentialMatchesHtml(similarityMatches) {
    const potentialMatches = similarityMatches?.potential_matches || [];
    
    if (potentialMatches.length === 0) {
        return '';
    }
    
    return `
        <div class="potential-matches">
            <h4>🔍 Potential Duplicates Found (${potentialMatches.length})</h4>
            ${potentialMatches.map(match => `
                <div class="match-item">
                    <div class="match-header">
                        <strong>${escapeHtml(match.title || 'Unknown Title')}</strong>
                        <span class="match-similarity">${Math.round((match.similarity || 0) * 100)}% similar</span>
                    </div>
                    <div class="match-details">
                        <span class="match-price">$${match.price ? match.price.toFixed(2) : 'N/A'}</span>
                        <span class="match-reason">${(match.match_reason || 'unknown').replace(/_/g, ' ')}</span>
                    </div>
                    <div class="match-actions">
                        <a href="${match.url}" target="_blank" class="btn-small">View Original</a>
                        ${match.shopify_id ? `<a href="https://admin.shopify.com/admin/products/${match.shopify_id}" target="_blank" class="btn-small">View in Shopify</a>` : ''}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function generateActionsHtml(reviewType, productId) {
    if (reviewType === 'duplicate_uncertain') {
        return `
            <button onclick="submitReview(${productId}, 'new_product')" class="action-btn btn-approve">New Product</button>
            <button onclick="submitReview(${productId}, 'duplicate')" class="action-btn btn-reject">Duplicate</button>
        `;
    } else {
        return `
            <button onclick="submitReview(${productId}, 'modest')" class="action-btn btn-approve">Modest</button>
            <button onclick="submitReview(${productId}, 'moderately_modest')" class="action-btn btn-needs-review">Moderately</button>
            <button onclick="submitReview(${productId}, 'not_modest')" class="action-btn btn-reject">Not Modest</button>
        `;
    }
}

function getReviewTypeBadge(reviewType) {
    if (reviewType === 'modesty_assessment') {
        return '<span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">👗 Modesty Review</span>';
    } else if (reviewType === 'duplicate_uncertain') {
        return '<span style="background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">🔍 Duplicate Check</span>';
    }
    return '';
}

function getConfidenceClass(score) {
    if (score > 0.85) return 'confidence-high';
    if (score > 0.7) return 'confidence-medium';
    return 'confidence-low';
}

function generateClothingTypeOptions(currentType) {
    const types = [
        { value: 'dress', label: 'Dress' },
        { value: 'top', label: 'Top' },
        { value: 'dress_top', label: 'Dress Top' },
        { value: 'bottom', label: 'Bottom' },
        { value: 'outerwear', label: 'Outerwear' },
        { value: 'other', label: 'Other/Accessory' }
    ];
    
    return types.map(type => {
        const selected = type.value === currentType ? 'selected' : '';
        return `<option value="${type.value}" ${selected}>${type.label}</option>`;
    }).join('\n');
}

// Submit review
async function submitReview(productId, decision, notes = '') {
    try {
        // Capture verified clothing type from dropdown
        const clothingTypeSelect = document.getElementById(`clothing_type_${productId}`);
        const clothingType = clothingTypeSelect ? clothingTypeSelect.value : null;
        
        if (!clothingType) {
            showToast('Please select a product type before submitting', 'error');
            return;
        }
        
        const response = await fetch('api/submit_review.php', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                product_id: productId,
                decision: decision,
                notes: notes,
                clothing_type: clothingType  // NEW: Include verified clothing type
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Remove product from view
            currentProducts = currentProducts.filter(p => p.id !== productId);
            renderProducts(currentProducts);
            showToast(result.message || 'Review submitted successfully!', 'success');
            
            // Refresh stats
            loadSystemStats();
        } else {
            throw new Error(result.error || 'Unknown error');
        }
        
    } catch (error) {
        console.error('Error submitting review:', error);
        showToast('Error submitting review: ' + error.message, 'error');
    }
}

// Show batch modal (placeholder)
function showBatchModal() {
    showToast('Batch export feature coming soon!', 'success');
}

// Logout
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        fetch('api/logout.php', { method: 'POST' })
            .then(() => {
                window.location.href = 'index.php';
            });
    }
}

// Toast notifications
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Utility functions
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text ? text.toString().replace(/[&<>"']/g, m => map[m]) : '';
}

