"""
Complete example: Template creation → Variant generation → Storage.

This demonstrates the full content generation pipeline.
"""

from src.agents.template_crafter import TemplateCrafter
from src.agents.parametric_generator import ParametricGenerator
from src.utils.database import TemplateDatabase, VariantDatabase
from src.models.template import Template
from src.models.variant import Variant


def example_complete_workflow():
    """Complete workflow with all components."""
    print("\n" + "=" * 70)
    print("COMPLETE WORKFLOW: Template → Variants → Storage")
    print("=" * 70)

    # Initialize components
    template_db = TemplateDatabase()
    variant_db = VariantDatabase()
    crafter = TemplateCrafter()
    generator = ParametricGenerator()

    # Step 1: Create Template
    print("\n[1/4] Creating template...")
    template_input = {
        "task_id": "demo_chain_rule",
        "course_id": "ap_calculus_bc",
        "unit_id": "u2_differentiation",
        "topic_id": "t3_chain_rule",
        "learning_objectives": [
            "Apply chain rule to composite functions",
            "Differentiate trigonometric compositions",
        ],
        "difficulty_target": [0.4, 0.7],
        "calculator_policy": "No-Calc",
        "misconceptions": [
            "Omitting inner derivative",
            "Confusing chain rule with product rule",
            "Incorrect trig derivative signs",
        ],
    }

    try:
        template_dict = crafter.create_template(template_input)
        template = Template(**template_dict)

        print(f"✅ Template created: {template.template_id}")
        print(f"   Course: {template.course_id}")
        print(f"   Topic: {template.topic_id}")
        print(f"   Parameters: {len(template.params)}")
        print(f"   Distractors: {len(template.distractor_rules)}")

    except Exception as e:
        print(f"❌ Template creation failed: {e}")
        return

    # Step 2: Save Template
    print("\n[2/4] Saving template to database...")
    try:
        template_db.save(template)
        print(f"✅ Template saved to: data/templates/{template.course_id}/")
    except Exception as e:
        print(f"❌ Template save failed: {e}")

    # Step 3: Generate Variants
    print("\n[3/4] Generating question variants...")
    try:
        variants = generator.generate_batch(
            template.model_dump(),
            count=20,
            seed_start=42,
        )

        print(f"✅ Generated {len(variants)}/20 variants")

        if variants:
            # Show sample variant
            sample = variants[0]
            print("\n📝 Sample Variant:")
            print(f"   ID: {sample['id']}")
            print(f"   Question: {sample['stimulus']}")
            print(f"   Options:")
            for i, opt in enumerate(sample['options']):
                marker = "✓" if i == sample['answer_index'] else " "
                print(f"     [{marker}] {i+1}. {opt}")

    except Exception as e:
        print(f"❌ Variant generation failed: {e}")
        return

    # Step 4: Save Variants
    print("\n[4/4] Saving variants to database...")
    try:
        variant_db.save_batch([Variant(**v) for v in variants])
        print(f"✅ Saved {len(variants)} variants")
        print(f"   Location: data/templates/variants/{template.course_id}/")
    except Exception as e:
        print(f"❌ Variant save failed: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE!")
    print("=" * 70)
    print(f"✅ Template: {template.template_id}")
    print(f"✅ Variants: {len(variants)} questions generated")
    print(f"✅ Storage: JSON files saved")
    print("\n📊 Statistics:")
    print(f"   - Template params: {len(template.params)}")
    print(f"   - Distractor rules: {len(template.distractor_rules)}")
    print(f"   - Generation success rate: {len(variants)/20*100:.1f}%")


def example_database_operations():
    """Demonstrate database operations."""
    print("\n" + "=" * 70)
    print("DATABASE OPERATIONS EXAMPLE")
    print("=" * 70)

    template_db = TemplateDatabase()
    variant_db = VariantDatabase()

    # List all templates
    print("\n[1] Listing all templates...")
    templates = template_db.list_templates()
    print(f"Found {len(templates)} templates:")
    for t in templates[:5]:  # Show first 5
        print(f"  - {t.template_id} ({t.course_id})")

    # List templates by course
    print("\n[2] Listing templates for AP Calculus BC...")
    calc_templates = template_db.list_templates(course_id="ap_calculus_bc")
    print(f"Found {len(calc_templates)} calculus templates")

    # List variants
    print("\n[3] Listing all variants...")
    all_variants = variant_db.list_variants()
    print(f"Found {len(all_variants)} total variants")

    # List variants by template
    if templates:
        template_id = templates[0].template_id
        print(f"\n[4] Listing variants for template: {template_id}...")
        template_variants = variant_db.list_variants(template_id=template_id)
        print(f"Found {len(template_variants)} variants for this template")


def example_parametric_generation():
    """Demonstrate parametric generation only."""
    print("\n" + "=" * 70)
    print("PARAMETRIC GENERATION EXAMPLE")
    print("=" * 70)

    # Create simple template
    template = Template(
        template_id="demo_simple_v1",
        created_by="demo",
        course_id="ap_calculus_bc",
        topic_id="derivatives",
        stem="Find the derivative of f(x) = {{a}}x^2 + {{b}}x",
        params={
            "a": {
                "type": "enum",
                "values": [1, 2, 3, 4, 5],
            },
            "b": {
                "type": "enum",
                "values": [1, 2, 3, 4, 5, -1, -2, -3],
            },
        },
        solution_template="2{{a}}x + {{b}}",
        distractor_rules=[
            {
                "rule_id": "forgot_power",
                "description": "Forgot to apply power rule correctly",
                "generation": "{{a}}x + {{b}}",
            },
            {
                "rule_id": "wrong_coef",
                "description": "Wrong coefficient",
                "generation": "{{a}}x + {{b}}",
            },
            {
                "rule_id": "added_constant",
                "description": "Added constant term",
                "generation": "2{{a}}x + {{b}} + C",
            },
        ],
    )

    print("\n📋 Template:")
    print(f"   Stem: {template.stem}")
    print(f"   Parameter space: {len(template.params['a']['values'])} × {len(template.params['b']['values'])} = {len(template.params['a']['values']) * len(template.params['b']['values'])} combinations")

    # Generate variants
    print("\n🎲 Generating 10 variants...")
    generator = ParametricGenerator()
    variants = generator.generate_batch(
        template.model_dump(),
        count=10,
        seed_start=0,
    )

    print(f"\n✅ Generated {len(variants)} variants:\n")
    for i, v in enumerate(variants[:5], 1):  # Show first 5
        print(f"{i}. {v['stimulus']}")
        print(f"   Answer: {v['solution']}")
        print()


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("APREP AI AGENTS - COMPLETE EXAMPLES")
    print("=" * 70)

    # Example 1: Parametric generation only
    example_parametric_generation()

    # Example 2: Complete workflow
    example_complete_workflow()

    # Example 3: Database operations
    example_database_operations()

    print("\n" + "=" * 70)
    print("ALL EXAMPLES COMPLETED!")
    print("=" * 70)
    print("\n💡 Next steps:")
    print("   1. Check data/templates/ for saved templates")
    print("   2. Check data/templates/variants/ for generated questions")
    print("   3. Run tests: pytest tests/")
    print("   4. Explore src/agents/ for implementation details")
    print()


if __name__ == "__main__":
    main()
