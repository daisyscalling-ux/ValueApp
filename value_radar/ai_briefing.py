name: value-radar-nightly

on:
  schedule:
    - cron: "15 5,13 * * *"     # 2x taeglich: ~07:15 & ~15:15 dt. Zeit
  workflow_dispatch: {}

jobs:
  precompute:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        working-directory: value_radar
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run nightly precompute
        working-directory: value_radar
        env:
          GSHEET_ID: ${{ secrets.GSHEET_ID }}
          GCP_SERVICE_ACCOUNT: ${{ secrets.GCP_SERVICE_ACCOUNT }}
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          FMP_API_KEY: ${{ secrets.FMP_API_KEY }}
          TIINGO_API_KEY: ${{ secrets.TIINGO_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          AI_BRIEFING_MODEL: ${{ secrets.AI_BRIEFING_MODEL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
        run: python precompute.py
