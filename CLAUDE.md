# Mode: Work

## The Rule

AI generates. I own everything that ships.

## AI Can

- Generate code, scaffolds, tests
- Explore alternatives
- Suggest better approaches

## Before Big Implementations

AI asks:

- "What are the constraints?"
- "What does failure look like?"

## After AI Generates

AI asks:

- "Can you walk through what this does?"
- "What would break this?"

## Red Flags (AI calls out)

- Accepting code without reading it
- "It works" without knowing why
- Asking for more before understanding previous output

---

## Project: Smart Cloud Optimizer

### Architecture

- `config.py` — project-wide constants, env vars, `setup_logging()`
- `aws_collector/config.py` — boto3 session & client factory (separate concern)
- `aws_collector/` — data collection pipeline (Cost Explorer, CloudWatch, Pricing, Inventory)
- `data_generation/synthetic.py` — synthetic data matching real CSV schemas
- `ai_module/`, `ml_engine/`, `optimizer/`, `storage/`, `dashboard/` — stub modules

### Data Flow

```text
synthetic.py  ──>  data/synthetic/*.csv  ──>  ml_engine (forecast)
                                          ──>  ai_module (LLM recs)
                                          ──>  optimizer (right-size)
aws_collector ──>  data/real/*.csv        ──>  same pipeline
```

### Code Style

- Module docstring: `"""filename.py — One-line.\n\nDetails.\n\nPart of the Smart Cloud Optimizer graduation project.\n"""`
- Type hints on all function signatures (params + return)
- Google-style docstrings (Args, Returns, Raises) on public functions
- Constants as `UPPER_SNAKE_CASE` at module top
- f-strings everywhere (no `.format()` or `%`)
- Imports: PEP 8 order (stdlib, third-party, local), alphabetical within groups
- Logging via `logging.getLogger(__name__)`, never `print()`
- Every external call (AWS API, file I/O) wrapped in try/except

### Key Commands

```bash
# Generate synthetic data
python -m data_generation.synthetic --output-dir data/synthetic/ --days 365 --seed 42

# Run tests
python -m pytest tests/ -v

# Run real AWS collection
python -m aws_collector.main

# Check imports work
python -c "from aws_collector import CollectorRunner"
```
