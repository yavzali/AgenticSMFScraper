<?php
session_start();

// Check authentication
if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
    header('Location: index.php');
    exit;
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Catalog Monitoring - Modesty Review Interface</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🕷️ Catalog Monitoring Review Interface</h1>
            <p>Review newly discovered products for modesty assessment and approve for scraping</p>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="pendingCount">-</div>
                    <div class="stat-label">Pending Review</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="approvedCount">-</div>
                    <div class="stat-label">Approved Today</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="totalProcessed">-</div>
                    <div class="stat-label">Total Processed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="lowConfidenceCount">-</div>
                    <div class="stat-label">Low Confidence</div>
                </div>
            </div>
        </div>

        <!-- Controls -->
        <div class="controls">
            <!-- Review Type Tabs -->
            <div class="filter-group" style="margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #eee;">
                <label style="font-weight: 700; color: #333; font-size: 1.1rem;">Review Type:</label>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="btn" id="modestyReviewTab" onclick="setReviewType('modesty_assessment')" 
                            style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        👗 Modesty Review
                    </button>
                    <button class="btn" id="duplicateReviewTab" onclick="setReviewType('duplicate_uncertain')"
                            style="background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);">
                        🔍 Duplicate Check
                    </button>
                    <button class="btn" id="allReviewTab" onclick="setReviewType('')"
                            style="background: linear-gradient(135deg, #888 0%, #666 100%);">
                        📋 All Products
                    </button>
                </div>
            </div>
            
            <div class="filter-group">
                <label for="retailerFilter">Retailer:</label>
                <select id="retailerFilter">
                    <option value="">All Retailers</option>
                    <option value="revolve">Revolve</option>
                    <option value="asos">ASOS</option>
                    <option value="aritzia">Aritzia</option>
                    <option value="anthropologie">Anthropologie</option>
                    <option value="uniqlo">Uniqlo</option>
                    <option value="hm">H&M</option>
                    <option value="mango">Mango</option>
                    <option value="abercrombie">Abercrombie</option>
                    <option value="nordstrom">Nordstrom</option>
                    <option value="urban_outfitters">Urban Outfitters</option>
                </select>

                <label for="categoryFilter">Category:</label>
                <select id="categoryFilter">
                    <option value="">All Categories</option>
                    <option value="dresses">Dresses</option>
                    <option value="tops">Tops</option>
                </select>

                <label for="confidenceFilter">Confidence:</label>
                <select id="confidenceFilter">
                    <option value="">All Confidence Levels</option>
                    <option value="low">Low (≤0.7)</option>
                    <option value="medium">Medium (0.7-0.85)</option>
                    <option value="high">High (>0.85)</option>
                </select>

                <button class="btn" onclick="loadProducts()">🔄 Refresh</button>
            </div>
        </div>

        <!-- Products Container -->
        <div id="products-container" class="products-container">
            <div class="loading">
                <div class="spinner"></div>
                Loading products for review...
            </div>
        </div>
    </div>

    <!-- Toast Notifications -->
    <div id="toast" class="toast"></div>

    <!-- Logout Button -->
    <button onclick="logout()" style="position: fixed; top: 20px; right: 20px; background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.3); padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
        Logout
    </button>

    <script src="assets/app.js"></script>
</body>
</html>

