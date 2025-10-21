"""
Complete workflow example with Solution Verification.

Demonstrates: Template creation → Variant generation → Solution verification → Storage
"""

from src.agents.template_crafter import TemplateCrafter
from src.agents.parametric_generator import ParametricGenerator
from src.agents.solution_verifier import SolutionVerifier, verify_batch
from src.utils.database import TemplateDatabase, VariantDatabase
from src.models.template import Template
from src.models.variant import Variant


def example_workflow_with_verification():
    """Complete workflow with verification."""
    print("\n" + "=" * 70)
    print("WORKFLOW: Template → Variants → Verification → Storage")
    print("=" * 70)

    # Initialize components
    template_db = TemplateDatabase()
    variant_db = VariantDatabase()
    crafter = TemplateCrafter()
    generator = ParametricGenerator()
    verifier = SolutionVerifier()

    # Step 1: Create Template
    print("\n[1/5] Creating template...")
    template_input = {
        "task_id": "demo_derivatives",
        "course_id": "ap_calculus_bc",
        "unit_id": "u2_differentiation",
        "topic_id": "t2_basic_derivatives",
        "learning_objectives": [
            "Calculate derivatives using power rule",
            "Apply chain rule to composite functions",
        ],
        "difficulty_target": [0.4, 0.7],
        "calculator_policy": "No-Calc",
        "misconceptions": [
            "Forgot to multiply by exponent",
            "Omitted chain rule inner derivative",
        ],
    }

    try:
        template_dict = crafter.create_template(template_input)
        template = Template(**template_dict)
        print(f"✅ Template created: {template.template_id}")
        print(f"   Parameters: {len(template.params)}")
        print(f"   Distractor rules: {len(template.distractor_rules)}")
    except Exception as e:
        print(f"❌ Template creation failed: {e}")
        return

    # Step 2: Save Template
    print("\n[2/5] Saving template...")
    try:
        template_db.save(template)
        print(f"✅ Template saved")
    except Exception as e:
        print(f"❌ Save failed: {e}")

    # Step 3: Generate Variants
    print("\n[3/5] Generating variants...")
    try:
        variants = generator.generate_batch(
            template.model_dump(), count=10, seed_start=42
        )
        print(f"✅ Generated {len(variants)} variants")
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return

    # Step 4: Verify Variants
    print("\n[4/5] Verifying mathematical correctness...")
    verification_results = []
    passed_count = 0
    failed_count = 0

    for i, variant in enumerate(variants, 1):
        print(f"\n   Verifying variant {i}/{len(variants)}...")
        try:
            result = verifier.verify_variant(variant)
            verification_results.append(result)

            status = result["verification_status"]
            confidence = result["consensus"]["confidence"]

            if status == "PASS":
                print(f"   ✅ PASS (confidence: {confidence:.2f})")
                passed_count += 1
            else:
                print(f"   ❌ FAIL (confidence: {confidence:.2f})")
                failed_count += 1
                if result["issues"]:
                    for issue in result["issues"]:
                        print(f"      Issue: {issue['description']}")

        except Exception as e:
            print(f"   ⚠️  Verification error: {e}")
            verification_results.append(
                {
                    "variant_id": variant.get("id", "unknown"),
                    "verification_status": "ERROR",
                }
            )

    print(f"\n   Verification Summary:")
    print(f"   - Passed: {passed_count}")
    print(f"   - Failed: {failed_count}")
    print(f"   - Pass Rate: {passed_count / len(variants) * 100:.1f}%")

    # Step 5: Store Only Verified Variants
    print("\n[5/5] Saving verified variants...")
    verified_variants = [
        Variant(**v)
        for i, v in enumerate(variants)
        if verification_results[i]["verification_status"] == "PASS"
    ]

    try:
        variant_db.save_batch(verified_variants)
        print(f"✅ Saved {len(verified_variants)} verified variants")
    except Exception as e:
        print(f"❌ Save failed: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE!")
    print("=" * 70)
    print(f"✅ Template: {template.template_id}")
    print(f"✅ Generated: {len(variants)} variants")
    print(f"✅ Verified: {passed_count} passed, {failed_count} failed")
    print(f"✅ Stored: {len(verified_variants)} verified variants")
    print(f"\n📊 Quality Metrics:")
    print(f"   - Generation success: {len(variants) / 10 * 100:.1f}%")
    print(f"   - Verification pass rate: {passed_count / len(variants) * 100:.1f}%")
    print(f"   - Overall quality: {len(verified_variants) / 10 * 100:.1f}%")


def example_batch_verification():
    """Demonstrate batch verification."""
    print("\n" + "=" * 70)
    print("BATCH VERIFICATION EXAMPLE")
    print("=" * 70)

    # Create simple test variants
    variants = [
        {
            "id": "test_v1",
            "stimulus": "Let f(x) = x². Find f'(x).",
            "options": ["2*x", "x", "2", "x²"],
            "answer_index": 0,
            "solution": "2*x",
        },
        {
            "id": "test_v2",
            "stimulus": "Let f(x) = x³. Find f'(x).",
            "options": ["3*x²", "x²", "3*x", "x³"],
            "answer_index": 0,
            "solution": "3*x**2",
        },
        {
            "id": "test_v3",
            "stimulus": "Let f(x) = sin(x). Find f'(x).",
            "options": ["cos(x)", "sin(x)", "-cos(x)", "tan(x)"],
            "answer_index": 0,
            "solution": "cos(x)",
        },
        {
            "id": "test_v4_wrong",
            "stimulus": "Let f(x) = x². Find f'(x).",
            "options": ["5*x", "x", "2", "x²"],  # Wrong answer!
            "answer_index": 0,
            "solution": "5*x",
        },
    ]

    print(f"\n[1/2] Verifying {len(variants)} test variants...")

    # Batch verification
    results = verify_batch(variants)

    print(f"\n[2/2] Verification complete!")
    print(f"\n📊 Results:")
    print(f"   - Total: {results['summary']['total']}")
    print(f"   - Passed: {results['summary']['passed']}")
    print(f"   - Failed: {results['summary']['failed']}")
    print(f"   - Needs Review: {results['summary']['needs_review']}")
    print(f"   - Pass Rate: {results['summary']['pass_rate'] * 100:.1f}%")

    # Show failed variants
    if results["failed"]:
        print(f"\n❌ Failed Variants:")
        for variant, result in results["failed"]:
            print(f"   - {variant['id']}: {result['issues'][0]['description']}")

    # Show variants needing review
    if results["needs_review"]:
        print(f"\n⚠️  Variants Needing Review:")
        for variant, result in results["needs_review"]:
            print(
                f"   - {variant['id']}: confidence={result['consensus']['confidence']:.2f}"
            )


def example_individual_verification():
    """Demonstrate detailed individual verification."""
    print("\n" + "=" * 70)
    print("DETAILED VERIFICATION EXAMPLE")
    print("=" * 70)

    verifier = SolutionVerifier()

    # Example 1: Correct derivative
    print("\n[Example 1] Correct derivative:")
    variant1 = {
        "id": "example_001",
        "stimulus": "Let f(x) = sin(2*x²). Find f'(x).",
        "options": ["4*x*cos(2*x²)", "cos(2*x²)", "2*x*cos(2*x²)", "sin(4*x)"],
        "answer_index": 0,
        "solution": "4*x*cos(2*x**2)",
    }

    result1 = verifier.verify_variant(variant1)
    print(f"   Status: {result1['verification_status']}")
    print(f"   Confidence: {result1['consensus']['confidence']:.2f}")
    print(f"   Symbolic: {result1['methods_used']['symbolic']['status']}")
    if "proof" in result1["methods_used"]["symbolic"]:
        print(f"   Proof: {result1['methods_used']['symbolic']['proof']}")

    # Example 2: Wrong derivative
    print("\n[Example 2] Wrong derivative:")
    variant2 = {
        "id": "example_002",
        "stimulus": "Let f(x) = x³. Find f'(x).",
        "options": ["5*x²", "x²", "3*x", "x³"],  # Wrong!
        "answer_index": 0,
        "solution": "5*x**2",
    }

    result2 = verifier.verify_variant(variant2)
    print(f"   Status: {result2['verification_status']}")
    print(f"   Issues: {len(result2['issues'])}")
    if result2["issues"]:
        print(f"   Issue: {result2['issues'][0]['description']}")
        if "evidence" in result2["issues"][0]:
            evidence = result2["issues"][0]["evidence"]
            if "symbolic_expected" in evidence:
                print(f"   Expected: {evidence['symbolic_expected']}")
                print(f"   Got: {evidence['symbolic_got']}")

    # Example 3: Distractor analysis
    print("\n[Example 3] Distractor analysis:")
    variant3 = {
        "id": "example_003",
        "stimulus": "Let f(x) = x². Find f'(x).",
        "options": ["2*x", "x", "2", "x²"],
        "answer_index": 0,
        "solution": "2*x",
    }

    result3 = verifier.verify_variant(variant3)
    print(f"   Distractor Analysis:")
    for dist in result3["distractor_analysis"]:
        status = "✅ Wrong" if dist["is_wrong"] else "❌ Correct (ISSUE!)"
        print(f"   - '{dist['value']}': {status}")
        print(f"     Reason: {dist['reason']}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("SOLUTION VERIFIER - COMPLETE EXAMPLES")
    print("=" * 70)

    # Example 1: Individual verification details
    example_individual_verification()

    # Example 2: Batch verification
    example_batch_verification()

    # Example 3: Complete workflow with verification
    example_workflow_with_verification()

    print("\n" + "=" * 70)
    print("ALL EXAMPLES COMPLETED!")
    print("=" * 70)
    print("\n💡 Next steps:")
    print("   1. Check data/templates/ for saved templates")
    print("   2. Check data/templates/variants/ for verified variants")
    print("   3. Run tests: pytest tests/unit/test_solution_verifier.py -v")
    print("   4. Integrate with your workflow")
    print()


if __name__ == "__main__":
    main()
