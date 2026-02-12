# AI Module

## Overview

The AI module provides **AI-powered architecture recommendations** for new users who don't have existing AWS usage data yet. It collects requirements through an interactive onboarding questionnaire, generates a custom prompt, calls Google Gemini 2.5 Flash, and stores the recommendations in the database.

```
                    ┌────────────────────────┐
                    │  Streamlit UI (ui.py)  │
                    │  Interactive form      │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  9 Guided Questions    │
                    │  (guided_questions.py) │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Prompt Builder        │
                    │  (prompt_builder.py)   │
                    │  Formats requirements  │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  AI Recommender        │
                    │  (recommender.py)      │
                    │  Google Gemini API     │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Parse & Validate JSON │
                    │  Extract structured    │
                    │  recommendation        │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Store in Database     │
                    │  ai_recommendations    │
                    │  table                 │
                    └────────────────────────┘
```

**Use Case**: Onboard users who want AWS architecture advice but don't have existing infrastructure to analyze. Replaces the need for manual consultation by providing instant, AI-powered recommendations tailored to their requirements.

## Architecture

### Components

#### 1. Guided Questions (`guided_questions.py`)

Returns a list of 9 structured questions to collect user requirements:

| ID | Question | Type | Purpose |
|----|----------|------|---------|
| `business_type` | What best describes your workload? | Select | Determine application architecture (web app, mobile backend, etc.) |
| `expected_users` | How many users do you expect? | Select | Size infrastructure appropriately |
| `uptime_requirement` | What are your uptime requirements? | Select | Decide on availability zones, backup strategies |
| `priority` | What is your top priority? | Select | Balance cost vs performance vs simplicity |
| `traffic_pattern` | How does your traffic behave? | Select | Choose scaling strategy (auto-scaling, serverless, etc.) |
| `availability` | How critical is availability? | Select | Multi-AZ, replication, failover configurations |
| `monthly_budget` | What is your monthly budget? | Select | Constraint for recommendations (Free Tier vs paid) |
| `experience_level` | Your AWS experience level? | Select | Adjust recommendation complexity (beginner = managed services) |
| `extra_notes` | Any additional requirements? | Text area | Free-form constraints (region, compliance, specific services) |

**Format:**
```python
{
    "id": "business_type",
    "question": "What best describes your workload?",
    "options": [
        "Web application (website, SaaS)",
        "Mobile backend (API for mobile apps)",
        "E-commerce platform",
        "Data analytics workload",
        "IoT / edge computing",
        "Internal tools / dashboards"
    ]
}
```

#### 2. Prompt Builder (`prompt_builder.py`)

Converts user answers into a detailed LLM prompt with:

**Context:**
- User profile (app type, users, uptime, budget, experience)
- Explicit goal: cost-optimized architecture

**Instructions:**
- Prefer serverless and Graviton-based instances
- Use modern instance families (t4g, m7g, c7g, r7g)
- Consider AWS Free Tier for tight budgets
- Match complexity to experience level
- Account for uptime requirements (single-AZ vs multi-AZ)

**Output Format Specification:**
```json
{
  "recommended_setup": {
    "compute": "detailed configuration",
    "database": "detailed configuration",
    "storage": "detailed configuration",
    "networking": "detailed configuration",
    "other_services": "any additional services"
  },
  "estimated_cost": 123.45,
  "explanation": "Detailed explanation covering why each service was chosen..."
}
```

**Safety:** Prompts the LLM to return **pure JSON only** (no markdown code blocks, no wrappers).

#### 3. AI Recommender (`recommender.py`)

Calls Google Gemini API with error handling and JSON extraction.

**Flow:**
```
1. Validate API key (config.GOOGLE_API_KEY)
2. Initialize GenerativeModel(config.GOOGLE_MODEL)
3. Generate content with temperature=0.3 (balanced creativity)
4. Extract JSON from response text (handles LLM wrapping JSON in markdown)
5. Parse and return structured dict

Error handling:
  - Missing API key → return {"error": "GOOGLE_API_KEY not set"}
  - API failure → return {"error": "API error: [details]"}
  - Invalid JSON → return {"error": "Failed to parse JSON"}
  - Empty response → return {"error": "API returned empty response"}
```

**Configuration (config.py):**
```python
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
```

**JSON Extraction (`extract_json()`):**
- Tries direct JSON parse first
- If fails, searches for `{` and `}` boundaries
- Handles markdown code blocks (```json ... ```)
- Raises ValueError if no valid JSON found

#### 4. Streamlit UI (`ui.py`)

Interactive web interface that:

1. **Displays form** with all 9 questions
2. **Collects answers** (selectbox for options, text_area for extra_notes)
3. **Generates prompt** via `build_prompt(user_answers)`
4. **Calls AI** via `get_ai_recommendations(prompt_text)`
5. **Handles errors** gracefully (shows user-friendly message)
6. **Stores results** in `ai_recommendations` table (via `storage.insert_ai_recommendations()`)
7. **Displays output:**
   - Recommended Setup (JSON)
   - Estimated Monthly Cost
   - Explanation (detailed reasoning)
   - Raw AI response (expandable)

**Database Schema Mapping:**
```python
{
    "app_type": user_answers["business_type"],
    "expected_users": user_answers.get("expected_users"),
    "uptime_hours": user_answers.get("uptime_requirement"),
    "importance": user_answers.get("availability"),
    "budget_monthly": user_answers.get("monthly_budget"),
    "extra_requirements": user_answers.get("extra_notes"),

    "prompt_text": prompt_text,
    "recommended_setup": json.dumps(structured["recommended_setup"]),  # Serialize dict to JSON
    "estimated_cost": structured["estimated_cost"],
    "explanation": structured["explanation"],

    "llm_model": "gemini-2.5-flash",
    "llm_response_raw": raw_output
}
```

**Important:** `recommended_setup` must be serialized with `json.dumps()` because SQLite doesn't support dict types.

## Usage

### Running the Streamlit App

```bash
# Set API key
export GOOGLE_API_KEY="your-api-key-here"

# Ensure project root is in PYTHONPATH
export PYTHONPATH=/path/to/cloud-gp:$PYTHONPATH

# Run Streamlit
streamlit run ai_module/ui.py
```

Open browser at http://localhost:8501 and fill out the form.

### Programmatic Usage

```python
from ai_module import get_guided_questions, build_prompt, get_ai_recommendations
import storage

# 1. Get questions
questions = get_guided_questions()

# 2. Collect answers (simulated)
user_answers = {
    "business_type": "Web application (website, SaaS)",
    "expected_users": "1,000-10,000",
    "uptime_requirement": "24x7 (always on)",
    "priority": "Balance cost and performance",
    "traffic_pattern": "Predictable daily peaks",
    "availability": "Must be highly available",
    "monthly_budget": "$500-2,000",
    "experience_level": "Intermediate (some AWS projects)",
    "extra_notes": "Must use us-west-2 region"
}

# 3. Build prompt
prompt_text = build_prompt(user_answers)

# 4. Get AI recommendations
structured, raw_output = get_ai_recommendations(prompt_text)

# 5. Check for errors
if "error" in structured:
    print(f"Error: {structured['error']}")
else:
    print(f"Recommended Setup: {structured['recommended_setup']}")
    print(f"Estimated Cost: ${structured['estimated_cost']}/mo")
    print(f"Explanation: {structured['explanation']}")

    # 6. Store in database
    conn = storage.get_connection()
    storage.insert_ai_recommendations(
        conn,
        user_id="aws-SYNTHETIC-001",
        rows=[{
            "app_type": user_answers["business_type"],
            "expected_users": user_answers.get("expected_users"),
            "uptime_hours": user_answers.get("uptime_requirement"),
            "importance": user_answers.get("availability"),
            "budget_monthly": user_answers.get("monthly_budget"),
            "extra_requirements": user_answers.get("extra_notes"),
            "prompt_text": prompt_text,
            "recommended_setup": json.dumps(structured["recommended_setup"]),
            "estimated_cost": structured["estimated_cost"],
            "explanation": structured["explanation"],
            "llm_model": "gemini-2.5-flash",
            "llm_response_raw": raw_output
        }]
    )
    conn.commit()
    conn.close()
```

## Testing

### Test Suite (`tests/test_ai_module.py`)

**12 tests across 3 test classes:**

#### TestGuidedQuestions (4 tests)
- Returns list of dicts
- Each question has required keys (id, question, options)
- All 9 required question IDs present
- extra_notes has empty options (text area)

#### TestPromptBuilder (3 tests)
- Builds prompt from answers dict
- Handles missing optional fields gracefully
- Specifies correct JSON output format

#### TestAIRecommender (5 tests)
- Successful API call returns parsed dict
- Handles API exceptions (returns error dict)
- Handles invalid JSON (returns error dict)
- Detects missing API key
- Handles empty API response

**Run tests:**
```bash
# Just ai_module tests
pytest tests/test_ai_module.py -v

# With coverage
pytest tests/test_ai_module.py --cov=ai_module --cov-report=term-missing
```

All tests use `unittest.mock.patch` to mock Google Gemini API calls (no real API requests in tests).

## Error Handling

The module is designed to **never crash**, only return structured errors:

| Error Type | Handling | User Experience |
|------------|----------|-----------------|
| Missing API key | Check at module load + function call | Clear error message in UI |
| API quota exceeded (429) | Catch exception, return error dict | "Quota exceeded, check billing" |
| Network failure | Catch exception, log, return error dict | "API error: [details]" |
| Invalid JSON response | Extract fails, return error dict | "Failed to parse JSON response" |
| Empty response | Check before parse, return error dict | "API returned empty response" |
| Malformed LLM output | JSON parse fails, return error dict | Show raw output in UI for debugging |

**Logging:**
All errors are logged to `logging.getLogger(__name__)` with details for debugging.

## Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Google Gemini (not OpenAI) | gemini-2.5-flash | Free tier, good JSON output, fast |
| 9 questions | Structured survey | Balance comprehensiveness vs UX burden |
| Temperature 0.3 | Balanced | Not too creative (0.7+), not deterministic (0.0) |
| JSON-only output | Strict format | Easy parsing, prevents hallucination in structure |
| Streamlit UI | Interactive forms | Fastest prototyping, no frontend code needed |
| Store raw LLM response | Full transparency | Allows debugging, audit trail |
| Error dict pattern | `{"error": "msg"}` | Consistent interface, easy to check |
| Separate prompt builder | Modular design | Testable, reusable, clear separation of concerns |

## Example Output

**Input (User Answers):**
- Business type: E-commerce platform
- Expected users: 10,000-100,000
- Uptime: 24x7
- Priority: Balance cost and performance
- Traffic: Unpredictable spikes (flash sales)
- Availability: Must be highly available
- Budget: $500-2,000
- Experience: Intermediate
- Extra: PCI-DSS compliance required

**AI Output:**
```json
{
  "recommended_setup": {
    "compute": "ECS Fargate with auto-scaling (0.5-4 vCPU tasks), Application Load Balancer",
    "database": "RDS for PostgreSQL (db.t4g.medium, Multi-AZ, read replica)",
    "storage": "S3 for product images (Standard-IA for old catalogs), CloudFront CDN",
    "networking": "VPC with 3 AZs, NAT gateways (2), VPC endpoints for S3",
    "other_services": "ElastiCache Redis (cache.t4g.micro) for session store, SQS for order queue, CloudWatch + SNS for alerts"
  },
  "estimated_cost": 875.25,
  "explanation": "This architecture is designed for an e-commerce platform with unpredictable traffic spikes...

  **Compute**: ECS Fargate eliminates server management and scales automatically during flash sales...

  **Database**: Multi-AZ RDS ensures high availability for PCI-DSS compliance. Read replica offloads reporting queries...

  **Cost Breakdown**:
  - Compute (Fargate): ~$350/mo (avg 2 vCPUs, burst to 8)
  - Database (RDS + replica): ~$280/mo
  - Storage (S3 + CloudFront): ~$120/mo
  - Cache (ElastiCache): ~$50/mo
  - Networking (NAT + ALB): ~$75/mo

  **Scaling**: Add more Fargate tasks (up to 20), upgrade RDS to db.m6g.large when traffic exceeds 100k users."
}
```

## Integration with Other Modules

- **Storage**: Uses `storage.insert_ai_recommendations()` to persist results
- **Config**: Reads `GOOGLE_API_KEY` and `GOOGLE_MODEL` from centralized config
- **Dashboard**: AI recommendations can be displayed alongside optimizer recommendations (future)

## Future Enhancements

1. **Multi-cloud support**: Add Azure, GCP options
2. **Cost comparison**: Show AI recommendation vs optimizer recommendation for existing users
3. **Iterative refinement**: Allow users to adjust answers and regenerate
4. **Export to Terraform**: Convert recommendations to IaC templates
5. **Feedback loop**: Let users rate recommendations, fine-tune prompts

---

*Part of the Smart Cloud Optimizer graduation project. Tested with Google Gemini 2.5 Flash API.*
