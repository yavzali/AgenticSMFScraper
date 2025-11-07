# PHASE 6: TESTING & VALIDATION - PROGRESS TRACKER

**Started**: 2025-11-07  
**Status**: IN PROGRESS

---

## OBJECTIVE

Validate that the new Dual Tower Architecture works correctly end-to-end.

**Key Goals**:
1. Test each workflow independently
2. Test with real retailer data
3. Compare results against v1.0 system
4. Validate no data loss
5. Performance benchmarking
6. Document any issues found

**Target**: Comprehensive testing to ensure migration success before cleanup

---

## TESTING STRATEGY

### Phase 6A: Unit Testing (Individual Workflows)
Test each workflow in isolation:
1. Product Updater
2. New Product Importer
3. Catalog Baseline Scanner
4. Catalog Monitor
5. Assessment Queue Manager

### Phase 6B: Integration Testing (End-to-End)
Test complete workflows:
1. Baseline → Monitor → Assessment → Review
2. Import → Modesty Assessment → Shopify Upload
3. Update → Shopify Sync

### Phase 6C: Retailer-Specific Testing
Test with actual retailers:
1. Markdown retailers (Revolve, Asos, Mango)
2. Patchright retailers (Anthropologie, Abercrombie, Urban Outfitters)
3. Verify all debugging knowledge preserved

### Phase 6D: Performance & Data Validation
1. Compare extraction quality (v1.0 vs v2.0)
2. Check API costs
3. Verify database integrity
4. Performance benchmarks

---

## COMPLETED

_(Nothing yet - just starting)_

---

## IN PROGRESS

### 🔄 Planning Test Cases (phase6-0)

**Test Matrix**:

| Workflow | Test Type | Retailer | Status |
|----------|-----------|----------|--------|
| Product Updater | Unit | Revolve | Pending |
| New Product Importer | Unit | Revolve | Pending |
| Catalog Baseline Scanner | Unit | Revolve | Pending |
| Catalog Monitor | Unit | Revolve | Pending |
| Assessment Queue | Unit | N/A | Pending |
| End-to-End | Integration | Revolve | Pending |
| Markdown Tower | Retailer | Revolve | Pending |
| Patchright Tower | Retailer | Anthropologie | Pending |

---

## PLANNED TEST CASES

### 1. Assessment Queue Manager Testing

**Test**: Basic queue operations
```bash
cd Shared
python assessment_queue_manager.py
```

**Expected**:
- ✅ Table created automatically
- ✅ Product added to queue
- ✅ Stats retrieved correctly
- ✅ Next item retrieved
- ✅ Marked as reviewed successfully

**Validation**:
- Check database: `sqlite3 products.db "SELECT * FROM assessment_queue"`
- Verify JSON fields parsed correctly
- Confirm priority ordering

---

### 2. Product Updater Testing

**Test**: Update existing Revolve products
```bash
cd Workflows
python product_updater.py --retailer revolve --limit 5
```

**Expected**:
- ✅ Queries DB for Revolve products with shopify_id
- ✅ Routes to Markdown Tower
- ✅ Extracts fresh data
- ✅ Updates in Shopify
- ✅ Updates local DB
- ✅ Sends notification

**Validation**:
- Check Shopify for updated prices/stock
- Verify local DB updated_at timestamp
- Check cost tracking
- Review logs for errors

---

### 3. New Product Importer Testing

**Test**: Import small batch of new products
```bash
cd Workflows
python new_product_importer.py ../Baseline\ URLs/batch_test_single.json --modesty-level modest
```

**Expected**:
- ✅ Loads batch file
- ✅ In-batch deduplication works
- ✅ Routes to appropriate tower
- ✅ Extracts product data
- ✅ Modesty assessment runs
- ✅ Uploads to Shopify if modest
- ✅ Saves to DB

**Validation**:
- Check products.db for new entries
- Verify Shopify upload (if modest)
- Check modesty_status field
- Verify checkpoint saved

---

### 4. Catalog Baseline Scanner Testing

**Test**: Establish baseline for small catalog
```bash
cd Workflows
python catalog_baseline_scanner.py revolve dresses modest --max-pages 2
```

**Expected**:
- ✅ Gets catalog URL from config
- ✅ Routes to Markdown Tower (Revolve)
- ✅ Extracts catalog products
- ✅ In-memory deduplication works
- ✅ Stores in catalog_products table
- ✅ Records metadata in catalog_baselines

**Validation**:
- Check catalog_products table
- Verify baseline_id created
- Check for duplicates
- Verify product count

---

### 5. Catalog Monitor Testing

**Test**: Monitor for new products (after updater runs)
```bash
cd Workflows
python catalog_monitor.py revolve dresses modest --max-pages 2
```

**Expected**:
- ✅ Scans catalog
- ✅ Routes to Markdown Tower
- ✅ Multi-level deduplication works
- ✅ Identifies new vs existing products
- ✅ Re-extracts new products with single extractor
- ✅ Adds to assessment queue (modesty)
- ✅ Adds suspected duplicates to queue (duplication)

**Validation**:
- Check assessment_queue table
- Verify new products added
- Check suspected duplicates
- Verify no false positives

---

### 6. Patchright Tower Testing (Anthropologie)

**Test**: Anthropologie catalog extraction (most complex)
```bash
cd Workflows
python catalog_baseline_scanner.py anthropologie dresses modest --max-pages 1
```

**Expected**:
- ✅ Routes to Patchright Tower
- ✅ PerimeterX verification handled (TAB + SPACE)
- ✅ Full-page screenshot captured
- ✅ Gemini Vision + DOM hybrid works
- ✅ DOM-first mode triggers (tall page)
- ✅ Products extracted successfully

**Validation**:
- Check if verification passed
- Verify product count
- Check extraction method used
- Verify all debugging logic preserved

---

### 7. End-to-End Integration Test

**Test**: Complete workflow from baseline to review

**Steps**:
1. Establish baseline (Revolve dresses)
2. Run Product Updater (update existing)
3. Run Catalog Monitor (detect new)
4. Check assessment queue
5. Manual review via PHP interface
6. Verify decisions recorded

**Expected**:
- ✅ All workflows connect seamlessly
- ✅ No data loss between steps
- ✅ Queue properly populated
- ✅ Decisions recorded correctly

---

### 8. Performance Benchmarking

**Metrics to Track**:
- Extraction time per product (Markdown vs Patchright)
- API costs (DeepSeek, Gemini, Jina AI)
- Database query performance
- Memory usage
- Total workflow time

**Comparison**:
- v1.0 (old architecture) vs v2.0 (Dual Tower)
- Expected: Similar or better performance
- Expected: Same or lower costs

---

### 9. Data Integrity Validation

**Checks**:
- ✅ All required fields populated
- ✅ No NULL values in critical fields
- ✅ JSON fields parse correctly
- ✅ Shopify IDs match
- ✅ No duplicate entries
- ✅ Timestamps accurate

**SQL Queries**:
```sql
-- Check for missing data
SELECT COUNT(*) FROM products WHERE title IS NULL OR price IS NULL;

-- Check assessment queue
SELECT review_type, status, COUNT(*) FROM assessment_queue GROUP BY review_type, status;

-- Check catalog baselines
SELECT retailer, category, total_products_seen FROM catalog_baselines ORDER BY baseline_date DESC;
```

---

## RISK ASSESSMENT

### High Risk Areas
1. **Patchright Verification**: PerimeterX/Cloudflare handling
2. **Deduplication Logic**: Fuzzy matching accuracy
3. **Assessment Queue**: PHP-Python integration
4. **Database Migration**: Old vs new tables

### Mitigation
- Start with small batches
- Test one retailer at a time
- Keep v1.0 system intact until validation complete
- Backup database before testing

---

## SUCCESS CRITERIA

**Phase 6 is successful if**:
- ✅ All 5 workflows run without errors
- ✅ Product data quality matches v1.0
- ✅ No data loss in database
- ✅ Assessment queue works end-to-end
- ✅ PHP interface connects to queue
- ✅ All retailer-specific debugging preserved
- ✅ Performance acceptable
- ✅ Costs similar or lower

**If any test fails**:
- Document the failure
- Fix the issue
- Re-test
- Do NOT proceed to Phase 7 (cleanup) until all tests pass

---

## TESTING LOG

### Session 1 (Current)
- Created Phase 6 progress tracker
- Defined test matrix
- Ready to start unit tests

**Next Steps**:
1. Test Assessment Queue Manager (CLI test)
2. Test Product Updater (5 products)
3. Test New Product Importer (batch_test_single.json)
4. Document results

---

**Last Updated**: 2025-11-07 (Session 1 - Planning)  
**Next Update**: After first test completes

---

## PHASE 6 STATUS: 0% COMPLETE (0/9 test cases, planning complete)

