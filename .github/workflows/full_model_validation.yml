name: Full Model Validation

# Validates the CURRENT live methodology (Technical + Fundamentals +
# Valuation + Analyst direction) by calling model.assemble_new_score()
# directly across historical data. This is a backtest over a fixed
# historical window -- re-running it against an unchanged model.py
# reproduces the exact same result, so there is no calendar schedule
# here. It runs when the thing it's validating actually changes (a push
# to model.py), or on demand.
on:
  push:
    branches: [main]
    paths:
      - 'model.py'
      - 'full_model_validation.py'
  workflow_dispatch:
    inputs:
      start:
        description: 'History start date (YYYY-MM-DD)'
        required: false
        default: '2022-01-01'
      step:
        description: 'Score every Nth trading day'
        required: false
        default: '5'

permissions:
  contents: write

concurrency:
  group: full-model-validation
  cancel-in-progress: false

env:
  PYTHONUNBUFFERED: '1'

jobs:
  validate:
    name: Validate the full live methodology against forward returns
    runs-on: ubuntu-latest
    timeout-minutes: 180
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - run: pip install -r requirements.txt

      - name: Restore point-in-time fundamentals cache
        uses: actions/cache@v4
        with:
          path: data/full_model_pit_cache
          key: full-model-pit-cache-${{ github.run_id }}
          restore-keys: full-model-pit-cache-

      - name: Run full model validation
        run: |
          python full_model_validation.py \
            --limit 1000 \
            --start "${{ github.event.inputs.start || '2022-01-01' }}" \
            --step "${{ github.event.inputs.step || '5' }}" \
            --output full_model_validation.csv \
            --summary public/data/full_model_validation.json

      - name: Keep the raw observations for further analysis
        uses: actions/upload-artifact@v4
        with:
          name: full-model-validation-rows
          path: |
            full_model_validation.csv
            full_model_validation_trade_events.csv
          retention-days: 30

      - name: Publish validation report
        run: |
          cp public/data/full_model_validation.json /tmp/full_model_validation.json
          git config user.name 'github-actions[bot]'
          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
          git fetch origin main
          git reset --hard origin/main
          mkdir -p public/data
          cp /tmp/full_model_validation.json public/data/full_model_validation.json
          git add public/data/full_model_validation.json
          git diff --cached --quiet && exit 0
          git commit -m 'Update full model validation [skip ci]'
          git push origin HEAD:main
