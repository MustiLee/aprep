"""Debug script to test variant generation locally."""

import json
import sys
sys.path.insert(0, '/Users/mustafayildirim/Documents/Personal Documents/Projects/Aprep/backend')

from src.agents.parametric_generator import ParametricGenerator
from src.utils.database import TemplateDatabase

# Load template
template_db = TemplateDatabase()
template = template_db.load("ap_calc_bc_t2_power_rule_polynomial_001")

print("=" * 60)
print("Template loaded:")
print(json.dumps(template.model_dump(), indent=2, default=str))
print("=" * 60)

# Try to generate ONE variant
generator = ParametricGenerator()
print("\nAttempting to generate 1 variant with seed=1000...")

try:
    variant = generator.generate_single_variant(template.model_dump(), seed=1000)
    print("\n✓ SUCCESS! Variant generated:")
    print(json.dumps(variant, indent=2, default=str))
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
