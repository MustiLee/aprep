# Sprint Execution Plan - Kritik Yol Haritası

**Date:** 2025-10-17
**Orchestrator:** Master Orchestrator
**Strategy:** Paralel + Sıralı Execution

---

## 🎯 Sprint 1-2: MCQ Fabrikası Tamamlama (3 Ajan)

### Durum
- ✅ Tamamlanan: 5/8 ajan
- ⏳ Kalan: 3/8 ajan

### Paralel Execution Group A (Week 1)
Dependency yokken paralel başlatılabilir:

#### Task 1.1: Misconception Database Manager
```json
{
  "task_id": "impl_misconception_db_mgr",
  "task_type": "agent_implementation",
  "priority": "high",
  "agent_name": "misconception-database-manager",
  "dependencies": [],
  "estimated_duration_hours": 16,
  "estimated_cost_usd": 5,
  "deliverables": [
    "src/agents/misconception_database_manager.py",
    "data/misconceptions/schema.json",
    "tests/unit/test_misconception_db_mgr.py"
  ],
  "acceptance_criteria": [
    "CRUD operations for misconceptions",
    "Category tagging (algebraic, conceptual, procedural)",
    "Search by topic/course",
    "Integration with Distractor Designer API"
  ]
}
```

**Can Start:** ✅ IMMEDIATELY (no dependencies)

#### Task 1.2: Taxonomy Manager
```json
{
  "task_id": "impl_taxonomy_manager",
  "task_type": "agent_implementation",
  "priority": "high",
  "agent_name": "taxonomy-manager",
  "dependencies": ["ced_parser"],
  "estimated_duration_hours": 12,
  "estimated_cost_usd": 3,
  "deliverables": [
    "src/agents/taxonomy_manager.py",
    "data/taxonomy/course_taxonomy.json",
    "tests/unit/test_taxonomy_manager.py"
  ],
  "acceptance_criteria": [
    "Course → Unit → Topic hierarchy",
    "LO tagging and mapping",
    "Difficulty level assignment",
    "Cross-reference with CED Parser output"
  ]
}
```

**Can Start:** ✅ IMMEDIATELY (CED Parser already exists)

---

### Sequential Execution (Week 1-2)

#### Task 1.3: Distractor Designer
**📋 Spec Reference:** `.claude/agents/distractor-designer.md`

```json
{
  "task_id": "impl_distractor_designer",
  "task_type": "agent_implementation",
  "priority": "critical",
  "agent_name": "distractor-designer",
  "spec_file": ".claude/agents/distractor-designer.md",
  "dependencies": [
    "misconception_database_manager",
    "parametric_generator"
  ],
  "estimated_duration_hours": 20,
  "estimated_cost_usd": 8,
  "deliverables": [
    "src/agents/distractor_designer.py",
    "tests/unit/test_distractor_designer.py",
    "tests/integration/test_template_to_distractor.py"
  ],
  "acceptance_criteria": [
    "Quality scoring (≥8/10)",
    "Pedagogical plausibility check",
    "Integration with Template Crafter",
    "Avoid trivial distractors",
    "MUST follow spec: ability targeting, selection rate estimation, set optimization"
  ]
}
```

**Can Start:** After Task 1.1 completes (needs misconception DB)

#### Task 1.4: Difficulty Calibrator
```json
{
  "task_id": "impl_difficulty_calibrator",
  "task_type": "agent_implementation",
  "priority": "high",
  "agent_name": "difficulty-calibrator",
  "dependencies": ["parametric_generator"],
  "estimated_duration_hours": 18,
  "estimated_cost_usd": 6,
  "deliverables": [
    "src/agents/difficulty_calibrator.py",
    "models/irt_lite_model.pkl",
    "tests/unit/test_difficulty_calibrator.py"
  ],
  "acceptance_criteria": [
    "IRT-lite (2PL model)",
    "Initial difficulty estimation",
    "Anchor items per topic",
    "Cold-start handling"
  ]
}
```

**Can Start:** ✅ IMMEDIATELY (Parametric Generator exists)

---

## 🎯 Sprint 3-4: Kalite Katmanı (4 Ajan)

### Paralel Execution Group B (Week 3)

#### Task 2.1: CED Alignment Validator
```json
{
  "task_id": "impl_ced_alignment_validator",
  "task_type": "agent_implementation",
  "priority": "critical",
  "agent_name": "ced-alignment-validator",
  "dependencies": ["template_crafter", "taxonomy_manager"],
  "estimated_duration_hours": 14,
  "estimated_cost_usd": 4,
  "deliverables": [
    "src/agents/ced_alignment_validator.py",
    "tests/unit/test_ced_alignment.py"
  ],
  "acceptance_criteria": [
    "LO mapping validation",
    "Curriculum coverage check",
    "Alignment score ≥0.90",
    "Flag off-topic content"
  ]
}
```

**Can Start:** After Task 1.2 (Taxonomy Manager)

#### Task 2.2: Plagiarism Detector
**📋 Spec Reference:** `.claude/agents/plagiarism-detector.md`

```json
{
  "task_id": "impl_plagiarism_detector",
  "task_type": "agent_implementation",
  "priority": "critical",
  "agent_name": "plagiarism-detector",
  "spec_file": ".claude/agents/plagiarism-detector.md",
  "dependencies": [],
  "estimated_duration_hours": 16,
  "estimated_cost_usd": 5,
  "deliverables": [
    "src/agents/plagiarism_detector.py",
    "tests/unit/test_plagiarism_detector.py"
  ],
  "acceptance_criteria": [
    "Similarity threshold <0.80",
    "TF-IDF + semantic embedding",
    "Compare against existing question bank",
    "Generate originality report",
    "MUST follow spec: embedding-based similarity, structural analysis, source-specific checking"
  ]
}
```

**Can Start:** ✅ IMMEDIATELY

---

### Paralel Execution Group C (Week 4)

#### Task 2.3: Readability Analyzer
**📋 Spec Reference:** `.claude/agents/readability-analyzer.md`

```json
{
  "task_id": "impl_readability_analyzer",
  "task_type": "agent_implementation",
  "priority": "medium",
  "agent_name": "readability-analyzer",
  "spec_file": ".claude/agents/readability-analyzer.md",
  "dependencies": [],
  "estimated_duration_hours": 12,
  "estimated_cost_usd": 3,
  "deliverables": [
    "src/agents/readability_analyzer.py",
    "tests/unit/test_readability.py"
  ],
  "acceptance_criteria": [
    "Flesch-Kincaid grade level",
    "Language complexity scoring",
    "Technical term density",
    "Flag overly complex questions",
    "MUST follow spec: multiple indices (Gunning Fog, SMOG, Coleman-Liau, ARI), passive voice detection, math adjustment"
  ]
}
```

**Can Start:** ✅ IMMEDIATELY

#### Task 2.4: Item Analyst
```json
{
  "task_id": "impl_item_analyst",
  "task_type": "agent_implementation",
  "priority": "high",
  "agent_name": "item-analyst",
  "dependencies": ["difficulty_calibrator"],
  "estimated_duration_hours": 16,
  "estimated_cost_usd": 5,
  "deliverables": [
    "src/agents/item_analyst.py",
    "tests/unit/test_item_analyst.py"
  ],
  "acceptance_criteria": [
    "p-value tracking (0.20-0.80)",
    "Point-biserial correlation (discrimination >0.30)",
    "Distractor analysis",
    "Flag problematic items"
  ]
}
```

**Can Start:** After Task 1.4 (Difficulty Calibrator)

---

## 📊 Execution Timeline

### Week 1 (Paralel Start)
```
Day 1-2: Kickoff
  ├─ Task 1.1: Misconception DB Manager [START]
  ├─ Task 1.2: Taxonomy Manager [START]
  └─ Task 1.4: Difficulty Calibrator [START]

Day 3-5: Development
  ├─ 1.1: CRUD ops + Schema
  ├─ 1.2: Hierarchy parsing
  └─ 1.4: IRT model implementation

Day 6-7: Testing + Integration
  ├─ 1.1: Unit tests [COMPLETE]
  ├─ 1.2: Integration tests [COMPLETE]
  └─ 1.4: Calibration tests [COMPLETE]
```

### Week 2 (Sequential + Paralel)
```
Day 1-3: Distractor Designer
  └─ Task 1.3: [START] → depends on 1.1

Day 4-7: Parallel quality agents
  ├─ Task 2.2: Plagiarism Detector [START]
  └─ Task 2.3: Readability Analyzer [START]
```

### Week 3 (Kalite Katmanı)
```
Day 1-5:
  ├─ Task 2.1: CED Alignment [START] → depends on 1.2
  └─ Task 2.4: Item Analyst [START] → depends on 1.4

Day 6-7: Integration testing
```

### Week 4 (Buffer + Polish)
```
Day 1-3: Integration testing
Day 4-5: Documentation
Day 6-7: Deploy to staging
```

---

## 🔄 Dependency Graph

```
┌─────────────────┐
│  CED Parser     │ (EXISTS ✅)
│  (Week 0)       │
└────────┬────────┘
         │
    ┌────┴─────┬──────────────┬───────────────┐
    │          │              │               │
┌───▼──────┐ ┌─▼───────────┐ │           ┌───▼─────────┐
│Taxonomy  │ │Template     │ │           │Parametric   │ (EXISTS ✅)
│Manager   │ │Crafter      │ (EXISTS ✅) │Generator    │
│(Week 1)  │ │(Week 0)     │ │           │(Week 0)     │
└───┬──────┘ └─┬───────────┘ │           └──┬──────────┘
    │          │              │              │
    │      ┌───┴──────┐   ┌───▼────────┐ ┌──▼──────────┐
    │      │Misconc.  │   │Difficulty  │ │Solution     │ (EXISTS ✅)
    │      │DB Mgr    │   │Calibrator  │ │Verifier     │
    │      │(Week 1)  │   │(Week 1-2)  │ │(Week 0)     │
    │      └───┬──────┘   └──┬─────────┘ └─────────────┘
    │          │             │
┌───▼──────────▼───┐     ┌──▼─────────┐
│CED Alignment     │     │Item        │
│Validator         │     │Analyst     │
│(Week 3)          │     │(Week 3-4)  │
└──────────────────┘     └────────────┘
         │
    ┌────┴─────┬──────────────┐
    │          │              │
┌───▼──────┐ ┌─▼───────────┐ ┌▼───────────┐
│Plagiarism│ │Readability  │ │Distractor  │
│Detector  │ │Analyzer     │ │Designer    │
│(Week 2-3)│ │(Week 2-3)   │ │(Week 2)    │
└──────────┘ └─────────────┘ └────────────┘
```

---

## 🚦 Execution Control

### Start Conditions
- ✅ **GREEN**: No dependencies, can start immediately
- 🟡 **YELLOW**: Waiting for 1 dependency
- 🔴 **RED**: Waiting for 2+ dependencies

### Current Status

**Week 1 - GREEN (Can Start Now):**
- ✅ Task 1.1: Misconception DB Manager
- ✅ Task 1.2: Taxonomy Manager
- ✅ Task 1.4: Difficulty Calibrator
- ✅ Task 2.2: Plagiarism Detector (paralel başlayabilir)
- ✅ Task 2.3: Readability Analyzer (paralel başlayabilir)

**Week 1-2 - YELLOW (Wait for 1.1):**
- 🟡 Task 1.3: Distractor Designer

**Week 3 - YELLOW (Wait for 1.2 or 1.4):**
- 🟡 Task 2.1: CED Alignment Validator (wait 1.2)
- 🟡 Task 2.4: Item Analyst (wait 1.4)

---

## 📈 Success Metrics

### Sprint 1-2 Success Criteria
- ✅ 3 new agents implemented
- ✅ MCQ fabrikası 100% complete (8/8)
- ✅ All unit tests passing
- ✅ Integration tests green
- ✅ Documentation complete

### Sprint 3-4 Success Criteria
- ✅ 4 kalite ajanı implemented
- ✅ End-to-end quality pipeline working
- ✅ Batch processing tested (100+ questions)
- ✅ Performance benchmarks met

---

## 🎯 Immediate Actions (TODAY)

1. **Start Paralel Group A:**
   ```bash
   # Create agent files
   - misconception_database_manager.py
   - taxonomy_manager.py
   - difficulty_calibrator.py
   ```

2. **Setup Infrastructure:**
   ```bash
   # Data directories
   mkdir -p data/misconceptions
   mkdir -p data/taxonomy
   mkdir -p models/irt
   ```

3. **Create Test Stubs:**
   ```bash
   # Test files
   tests/unit/test_misconception_db_mgr.py
   tests/unit/test_taxonomy_manager.py
   tests/unit/test_difficulty_calibrator.py
   ```

---

**Orchestrator Approval:** ✅ READY TO EXECUTE
**Risk Level:** LOW (clear dependencies, proven architecture)
**Estimated Completion:** 4 weeks
**Total New Agents:** 7 (Sprint 1-2: 3, Sprint 3-4: 4)
