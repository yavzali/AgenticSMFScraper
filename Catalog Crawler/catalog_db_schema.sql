-- ===================================================================
-- CATALOG MONITORING DATABASE SCHEMA EXTENSIONS
-- Extends existing products.db with catalog monitoring functionality
-- ===================================================================

-- 1. Catalog Products Table
-- Stores discovered products pending/completed modesty review
CREATE TABLE IF NOT EXISTS catalog_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Product Identification
    product_code VARCHAR(100),              -- Extracted from URL (e.g., 'E443577-000' from Uniqlo)
    catalog_url VARCHAR(1000) NOT NULL,    -- URL found in catalog
    normalized_url VARCHAR(1000),          -- Cleaned URL for matching
    retailer VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,        -- 'dresses' or 'tops'
    
    -- Product Data (from catalog extraction)
    title VARCHAR(500),
    price DECIMAL(10,2),
    original_price DECIMAL(10,2),
    sale_status VARCHAR(50),               -- 'on_sale', 'regular', 'clearance'
    image_urls TEXT,                       -- JSON array of image URLs
    availability VARCHAR(50),              -- 'in_stock', 'low_stock', 'out_of_stock'
    
    -- Discovery & Processing
    discovered_date DATE NOT NULL,
    discovery_run_id VARCHAR(100),         -- Links to catalog_monitoring_runs
    extraction_method VARCHAR(50),         -- 'markdown' or 'playwright'
    
    -- Modesty Review Status
    review_status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'modest', 'moderately_modest', 'immodest', 'needs_review'
    reviewed_by VARCHAR(100),
    reviewed_date TIMESTAMP,
    review_notes TEXT,
    
    -- New Product Detection
    is_new_product BOOLEAN DEFAULT 1,      -- 1 = new, 0 = existing (baseline)
    similarity_matches TEXT,               -- JSON of potential matches found
    confidence_score DECIMAL(3,2),         -- 0-1 confidence in new product detection
    
    -- Processing Status
    approved_for_scraping BOOLEAN DEFAULT 0,  -- Ready for batch creation
    batch_created BOOLEAN DEFAULT 0,       -- Added to approved batch
    batch_file VARCHAR(200),              -- Name of created batch file
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Catalog Baselines Table  
-- Tracks when initial catalog reviews completed per retailer/category
CREATE TABLE IF NOT EXISTS catalog_baselines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Baseline Identification
    retailer VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,        -- 'dresses' or 'tops'
    baseline_date DATE NOT NULL,           -- Date of manual review
    
    -- Baseline Data
    total_products_seen INTEGER NOT NULL,  -- Total products in baseline crawl
    crawl_pages INTEGER,                   -- Number of pages crawled
    crawl_depth_reached VARCHAR(100),      -- How deep we went (e.g., 'page_5', '200_products')
    extraction_method VARCHAR(50),         -- 'markdown' or 'playwright'
    
    -- URLs & Configuration
    catalog_url VARCHAR(1000),             -- Base catalog URL used
    sort_by_newest_url VARCHAR(1000),      -- Sorted URL for ongoing monitoring
    
    -- Crawl Strategy
    pagination_type VARCHAR(50),           -- 'pagination', 'infinite_scroll', 'hybrid'
    has_sort_by_newest BOOLEAN DEFAULT 1,
    early_stop_threshold INTEGER DEFAULT 3,  -- Stop after N consecutive existing products
    
    -- Status & Validation
    baseline_status VARCHAR(50) DEFAULT 'active',  -- 'active', 'needs_refresh', 'deprecated'
    last_validated TIMESTAMP,
    validation_notes TEXT,
    
    -- Performance Tracking
    baseline_crawl_time DECIMAL(8,2),      -- Time taken for baseline (seconds)
    avg_products_per_page DECIMAL(5,1),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(retailer, category, baseline_date)
);

-- 3. Catalog Monitoring Runs Table
-- Historical run data for performance tracking and debugging
CREATE TABLE IF NOT EXISTS catalog_monitoring_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Run Identification
    run_id VARCHAR(100) UNIQUE NOT NULL,   -- UUID for this monitoring run
    run_type VARCHAR(50) NOT NULL,         -- 'baseline_establishment', 'weekly_monitoring', 'manual_refresh'
    
    -- Run Scope
    retailer VARCHAR(100),                 -- NULL for all-retailer runs
    category VARCHAR(100),                 -- NULL for all-category runs
    scheduled_time TIMESTAMP,              -- When run was scheduled
    actual_start_time TIMESTAMP,           -- When run actually started
    
    -- Run Configuration
    crawl_strategy VARCHAR(50),            -- 'newest_first', 'full_catalog', 'partial_refresh'
    max_pages INTEGER,                     -- Limit for this run
    early_stop_enabled BOOLEAN DEFAULT 1,
    
    -- Results Summary
    total_products_crawled INTEGER DEFAULT 0,
    new_products_found INTEGER DEFAULT 0,
    existing_products_encountered INTEGER DEFAULT 0,
    pages_crawled INTEGER DEFAULT 0,
    
    -- Performance Metrics
    total_runtime DECIMAL(8,2),            -- Total seconds
    avg_time_per_page DECIMAL(5,2),
    api_calls_made INTEGER DEFAULT 0,
    total_cost DECIMAL(8,4),               -- Total API cost
    
    -- Status & Results
    run_status VARCHAR(50),                -- 'completed', 'failed', 'partial', 'cancelled'
    error_count INTEGER DEFAULT 0,
    completion_percentage DECIMAL(5,2),    -- % of planned work completed
    
    -- Output
    products_for_review INTEGER DEFAULT 0, -- New products needing modesty review
    batch_files_created TEXT,              -- JSON array of created batch files
    
    -- Timestamps
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Catalog Errors Table
-- Detailed error tracking for debugging and pattern recognition
CREATE TABLE IF NOT EXISTS catalog_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Error Context
    run_id VARCHAR(100),                   -- Links to catalog_monitoring_runs
    retailer VARCHAR(100),
    category VARCHAR(100),
    crawler_type VARCHAR(50),              -- 'markdown', 'playwright'
    
    -- Error Details
    error_type VARCHAR(100),               -- 'extraction_failed', 'network_timeout', 'anti_bot_detected'
    error_message TEXT,
    error_traceback TEXT,
    
    -- Context Information
    url_attempted VARCHAR(1000),
    page_number INTEGER,
    retry_attempt INTEGER DEFAULT 1,
    
    -- Impact Assessment
    severity VARCHAR(50),                  -- 'low', 'medium', 'high', 'critical'
    impact_on_run VARCHAR(100),           -- 'continued', 'retry_successful', 'run_aborted'
    
    -- Resolution
    resolved BOOLEAN DEFAULT 0,
    resolution_notes TEXT,
    
    -- Timestamps
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- ===================================================================
-- INDEXES FOR PERFORMANCE
-- ===================================================================

-- Catalog Products Indexes
CREATE INDEX IF NOT EXISTS idx_catalog_products_retailer_category 
    ON catalog_products(retailer, category);
CREATE INDEX IF NOT EXISTS idx_catalog_products_discovery_run 
    ON catalog_products(discovery_run_id);
CREATE INDEX IF NOT EXISTS idx_catalog_products_review_status 
    ON catalog_products(review_status);
CREATE INDEX IF NOT EXISTS idx_catalog_products_normalized_url 
    ON catalog_products(normalized_url);
CREATE INDEX IF NOT EXISTS idx_catalog_products_product_code 
    ON catalog_products(product_code, retailer);
CREATE INDEX IF NOT EXISTS idx_catalog_products_discovered_date 
    ON catalog_products(discovered_date);

-- Catalog Baselines Indexes  
CREATE INDEX IF NOT EXISTS idx_catalog_baselines_retailer_category 
    ON catalog_baselines(retailer, category);
CREATE INDEX IF NOT EXISTS idx_catalog_baselines_status 
    ON catalog_baselines(baseline_status);

-- Monitoring Runs Indexes
CREATE INDEX IF NOT EXISTS idx_catalog_runs_run_id 
    ON catalog_monitoring_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_catalog_runs_retailer_category 
    ON catalog_monitoring_runs(retailer, category);
CREATE INDEX IF NOT EXISTS idx_catalog_runs_scheduled_time 
    ON catalog_monitoring_runs(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_catalog_runs_status 
    ON catalog_monitoring_runs(run_status);

-- Errors Indexes
CREATE INDEX IF NOT EXISTS idx_catalog_errors_run_id 
    ON catalog_errors(run_id);
CREATE INDEX IF NOT EXISTS idx_catalog_errors_retailer_type 
    ON catalog_errors(retailer, error_type);
CREATE INDEX IF NOT EXISTS idx_catalog_errors_occurred_at 
    ON catalog_errors(occurred_at);

-- ===================================================================
-- SAMPLE DATA VIEWS FOR MONITORING
-- ===================================================================

-- View: Pending Review Products
CREATE VIEW IF NOT EXISTS pending_review_summary AS
SELECT 
    retailer,
    category,
    COUNT(*) as pending_products,
    MIN(discovered_date) as oldest_discovery,
    MAX(discovered_date) as newest_discovery
FROM catalog_products 
WHERE review_status = 'pending'
GROUP BY retailer, category;

-- View: Baseline Status
CREATE VIEW IF NOT EXISTS baseline_status_summary AS
SELECT 
    retailer,
    category,
    baseline_date,
    total_products_seen,
    baseline_status,
    CASE 
        WHEN baseline_status = 'active' AND last_validated < date('now', '-30 days') 
        THEN 'needs_validation'
        ELSE baseline_status 
    END as recommended_action
FROM catalog_baselines
ORDER BY retailer, category;

-- View: Recent Run Performance
CREATE VIEW IF NOT EXISTS recent_run_performance AS
SELECT 
    run_id,
    retailer || ' - ' || category as scope,
    run_type,
    new_products_found,
    total_runtime,
    ROUND(total_cost, 4) as cost,
    run_status,
    actual_start_time
FROM catalog_monitoring_runs 
WHERE actual_start_time > date('now', '-7 days')
ORDER BY actual_start_time DESC;