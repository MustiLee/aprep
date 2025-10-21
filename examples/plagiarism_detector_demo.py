"""
Plagiarism Detector V2 - Demo Script

This script demonstrates the full capabilities of the Plagiarism Detector V2:
- Setting up embedding services (Voyage AI / OpenAI)
- Configuring ChromaDB vector database
- Adding questions to the database
- Checking for plagiarism
- Generating comprehensive reports

Usage:
    python examples/plagiarism_detector_demo.py

Note: Requires VOYAGE_API_KEY or OPENAI_API_KEY environment variable
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.embedding_service import (
    VoyageEmbeddingService,
    OpenAIEmbeddingService,
    CachedEmbeddingService
)
from src.services.vector_database import ChromaDBDatabase
from src.agents.plagiarism_detector_v2 import (
    PlagiarismDetectorV2,
    SourceType
)


def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_report_summary(report):
    """Print plagiarism report summary"""
    print(f"Check ID: {report.check_id}")
    print(f"Content ID: {report.content_id}")
    print(f"\nOverall Assessment:")
    print(f"  Status: {report.overall_assessment['status']}")
    print(f"  Max Similarity: {report.overall_assessment['max_similarity']:.2%}")
    print(f"  Pass: {report.overall_assessment['pass']}")
    print(f"  Confidence: {report.overall_assessment['confidence']:.2%}")

    print(f"\nRisk Assessment:")
    print(f"  Copyright Risk: {report.risk_assessment.copyright_risk.value}")
    print(f"  Originality Score: {report.risk_assessment.originality_score:.2%}")
    print(f"  Recommendation: {report.risk_assessment.recommendation}")
    print(f"  Requires Review: {report.risk_assessment.requires_review}")
    print(f"  Legal Review: {report.risk_assessment.legal_review_required}")

    if report.high_similarity_matches.get("found"):
        print(f"\n⚠️  HIGH SIMILARITY MATCHES: {len(report.high_similarity_matches['matches'])}")
        for match in report.high_similarity_matches["matches"][:3]:
            print(f"  - {match['source_id']}: {match['similarity_score']:.2%} ({match['source_type']})")

    if report.moderate_similarity_matches.get("found"):
        print(f"\n📊 MODERATE SIMILARITY: {report.moderate_similarity_matches['count']} matches")

    if report.escalation:
        print(f"\n🚨 ESCALATION:")
        print(f"  To: {', '.join(report.escalation['escalate_to'])}")
        print(f"  Urgency: {report.escalation['urgency']}")
        print(f"  Reason: {report.escalation['reason']}")


def main():
    """Main demo script"""

    print_section("Plagiarism Detector V2 - Demo Script")

    # Check for API keys
    voyage_key = os.getenv("VOYAGE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not voyage_key and not openai_key:
        print("⚠️  WARNING: No API keys found!")
        print("Set VOYAGE_API_KEY or OPENAI_API_KEY environment variable")
        print("\nUsing mock embedding service for demo purposes...")

        # Create mock embedding service
        from tests.unit.services.test_embedding_service import MockEmbeddingService
        embedding_service = MockEmbeddingService(dimensions=1536)
    else:
        # Step 1: Setup Embedding Service
        print_section("Step 1: Setting up Embedding Service")

        if voyage_key:
            print("✓ Using Voyage AI (primary)")
            base_service = VoyageEmbeddingService(
                api_key=voyage_key,
                model="voyage-large-2"
            )
        else:
            print("✓ Using OpenAI (fallback)")
            base_service = OpenAIEmbeddingService(
                api_key=openai_key,
                model="text-embedding-3-large"
            )

        # Wrap with caching
        embedding_service = CachedEmbeddingService(
            base_service=base_service,
            cache_dir="data/demo_embedding_cache",
            ttl_days=30
        )
        print(f"✓ Caching enabled (cache_dir: data/demo_embedding_cache)")

    # Step 2: Setup Vector Database
    print_section("Step 2: Setting up Vector Database")

    vector_db = ChromaDBDatabase(
        collection_name="demo_questions",
        persist_directory="data/demo_chromadb",
        distance_metric="cosine"
    )
    print(f"✓ ChromaDB initialized")
    print(f"  Collection: demo_questions")
    print(f"  Documents: {vector_db.get_document_count()}")

    # Step 3: Initialize Plagiarism Detector
    print_section("Step 3: Initializing Plagiarism Detector V2")

    detector = PlagiarismDetectorV2(
        embedding_service=embedding_service,
        vector_database=vector_db,
        similarity_threshold=0.80
    )
    print("✓ Plagiarism Detector V2 ready")
    print(f"  Similarity Threshold: {detector.similarity_threshold}")
    print(f"  Database Size: {vector_db.get_document_count()}")

    # Step 4: Add Sample Questions to Database
    print_section("Step 4: Adding Sample Questions to Database")

    sample_questions = [
        {
            "id": "ap_calc_001",
            "content": {
                "stimulus": "Find the derivative of f(x) = 3x^2 + 5x - 2",
                "options": ["6x + 5", "3x + 5", "6x - 2", "3x"]
            },
            "source_type": SourceType.AP_RELEASED,
            "metadata": {"year": 2019, "difficulty": "medium"}
        },
        {
            "id": "textbook_001",
            "content": {
                "stimulus": "Evaluate the integral: ∫(2x + 3) dx",
                "options": ["x^2 + 3x + C", "2x^2 + 3x + C", "x^2 + C", "2x + C"]
            },
            "source_type": SourceType.TEXTBOOK,
            "metadata": {"book": "Stewart Calculus", "chapter": 5}
        },
        {
            "id": "internal_001",
            "content": {
                "stimulus": "Find the limit: lim (x→0) sin(x)/x",
                "options": ["1", "0", "∞", "undefined"]
            },
            "source_type": SourceType.INTERNAL,
            "metadata": {"created_by": "system", "version": 1}
        },
        {
            "id": "textbook_002",
            "content": {
                "stimulus": "Use the chain rule to find the derivative of h(x) = sin(x^2)",
                "options": ["2x cos(x^2)", "cos(x^2)", "2x sin(x^2)", "x cos(x^2)"]
            },
            "source_type": SourceType.TEXTBOOK,
            "metadata": {"book": "Larson Calculus", "chapter": 3}
        }
    ]

    for q in sample_questions:
        detector.add_to_database(
            question_id=q["id"],
            content=q["content"],
            source_type=q["source_type"],
            metadata=q["metadata"]
        )
        print(f"✓ Added: {q['id']} ({q['source_type'].value})")

    print(f"\n✓ Database now contains {vector_db.get_document_count()} questions")

    # Step 5: Test Case 1 - Original Question (Low Similarity)
    print_section("Test Case 1: Original Question (Low Similarity)")

    original_question = {
        "stimulus": "Calculate the second derivative of g(x) = e^(2x) + ln(x)",
        "options": ["4e^(2x) - 1/x^2", "2e^(2x) - 1/x^2", "4e^(2x) + 1/x", "2e^(2x) + 1/x^2"]
    }

    print("Checking question:")
    print(f"  '{original_question['stimulus']}'")
    print()

    report1 = detector.check_content(
        content=original_question,
        content_id="test_original_001"
    )

    print_report_summary(report1)

    # Step 6: Test Case 2 - Similar Question (Moderate Similarity)
    print_section("Test Case 2: Similar Question (Moderate Similarity)")

    similar_question = {
        "stimulus": "Find the derivative of f(x) = 3x^2 + 5x",
        "options": ["6x + 5", "3x", "6x", "3x + 5"]
    }

    print("Checking question:")
    print(f"  '{similar_question['stimulus']}'")
    print()

    report2 = detector.check_content(
        content=similar_question,
        content_id="test_similar_001"
    )

    print_report_summary(report2)

    # Step 7: Test Case 3 - Very Similar Question (High Similarity)
    print_section("Test Case 3: Very Similar Question (High Similarity)")

    very_similar_question = {
        "stimulus": "Find the derivative of f(x) = 3x² + 5x - 2",  # Almost identical
        "options": ["6x + 5", "3x + 5", "6x - 2", "3x"]
    }

    print("Checking question:")
    print(f"  '{very_similar_question['stimulus']}'")
    print()

    report3 = detector.check_content(
        content=very_similar_question,
        content_id="test_high_similarity_001"
    )

    print_report_summary(report3)

    # Step 8: Statistics
    print_section("Step 8: Detection Statistics")

    stats = detector.get_statistics()

    print(f"Total Checks: {stats['total_checks']}")
    print(f"Total Flagged: {stats['total_flagged']}")
    print(f"Flag Rate: {stats['flag_rate']:.1%}")
    print(f"Database Size: {stats['database_size']} questions")
    print(f"Similarity Threshold: {stats['similarity_threshold']}")

    if "embedding_cache_stats" in stats and stats["embedding_cache_stats"]:
        cache_stats = stats["embedding_cache_stats"]
        print(f"\nEmbedding Cache:")
        print(f"  Cache Hits: {cache_stats['cache_hits']}")
        print(f"  Cache Misses: {cache_stats['cache_misses']}")
        print(f"  Hit Rate: {cache_stats['hit_rate']:.1%}")

    # Step 9: Summary
    print_section("Demo Complete!")

    print("✅ Successfully demonstrated:")
    print("  • Embedding service setup (Voyage AI / OpenAI)")
    print("  • Vector database configuration (ChromaDB)")
    print("  • Adding questions to database")
    print("  • Checking for plagiarism")
    print("  • Generating comprehensive reports")
    print("  • Statistics tracking")
    print()
    print("🎯 Plagiarism Detector V2 is ready for production!")
    print()
    print("Next steps:")
    print("  1. Load your question database")
    print("  2. Set similarity thresholds per source type")
    print("  3. Integrate with Master Orchestrator")
    print("  4. Setup HITL review workflow")
    print()
    print("For more information, see:")
    print("  - Spec: .claude/agents/plagiarism-detector.md")
    print("  - Tests: tests/unit/test_plagiarism_detector_v2_*.py")
    print("  - Docs: SPRINT_3_4_COMPLETION_REPORT.md")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
