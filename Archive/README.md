# Archive - Historical Documentation

**Purpose**: This folder contains superseded documentation that has been consolidated into the `/Knowledge/` directory.

**Status**: Archived (2025-11-07)

---

## Archived Files

### Retailer-Specific Documentation
- **`PERIMETERX_BREAKTHROUGH.md`** → Consolidated into `Knowledge/RETAILER_PLAYBOOK.md` (Anthropologie section)
- **`ANTHROPOLOGIE_TEST_PLAN.md`** → Consolidated into `Knowledge/RETAILER_PLAYBOOK.md`
- **`REVOLVE_URL_CHANGE_FINDINGS.md`** → Consolidated into `Knowledge/RETAILER_PLAYBOOK.md` (Revolve section)

### Testing Documentation
- **`PATCHRIGHT_CATALOG_TESTING_PLAN.md`** → Consolidated into `Knowledge/RETAILER_PLAYBOOK.md` (Quick Reference Matrix)
- **`PATCHRIGHT_CATALOG_TEST_LOG.md`** → Consolidated into `Knowledge/DEBUGGING_LESSONS.md`

### Design Decisions
- **`CATALOG_EXTRACTION_DECISIONS.md`** → Consolidated into `Knowledge/DEBUGGING_LESSONS.md` (DOM vs Gemini Vision section)

---

## New Knowledge Base Structure

All information from archived files has been reorganized into:

### `/Knowledge/` Directory
1. **`RETAILER_PLAYBOOK.md`** - Retailer-specific solutions and working strategies
2. **`DEBUGGING_LESSONS.md`** - Technical lessons learned, common issues and solutions
3. **`RETAILER_CONFIG.json`** - High-level strategies and configuration for all retailers
4. **`learned_patterns_export.json`** - Low-level DOM selectors learned by pattern learner
5. **`WEB_ASSESSMENT_GUIDE.md`** - Complete documentation for the assessment pipeline
6. **`DUAL_TOWER_MIGRATION_PLAN.md`** - Architecture redesign plan and progress

---

## Why These Files Were Archived

**Reason**: As the system grew, documentation became fragmented across many single-purpose files. This made it:
- Hard to find relevant information
- Difficult to maintain consistency
- Challenging to onboard new developers
- Prone to duplication

**Solution**: Consolidated all knowledge into 6 comprehensive, well-organized files in `/Knowledge/` directory.

**Benefit**:
- ✅ Single source of truth per topic
- ✅ Cross-referenced and consistent
- ✅ Easier to search and navigate
- ✅ Prepared for dual tower architecture migration

---

## Should You Use These Files?

**No** - Use the `/Knowledge/` directory instead.

These files are kept for:
- Historical reference
- Audit trail of debugging process
- Preserving context of decisions made

**Current Documentation**: `/Knowledge/` directory  
**Migration Plan**: `/Knowledge/DUAL_TOWER_MIGRATION_PLAN.md`

---

**Last Updated**: 2025-11-07  
**Phase**: 0 (Knowledge Preservation) - Complete

