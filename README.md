# X Analytics Project

## Important
This is a best-effort collector for content rendered on publicly accessible X profile pages. It does not log in, call private endpoints, bypass access controls, or solve CAPTCHAs. X may restrict automated access or change its interface. Only collect data where you have permission and in compliance with X's terms and applicable law. If a login wall or rate limit appears, stop; do not repeatedly retry. You can upload an authorized CSV export to the dashboard instead.

Engagement labels are read from the visible page and may be unavailable or zero if X changes its UI. Views may not be displayed. Sentiment uses VADER as a simple baseline, not a definitive interpretation.

## Windows installation
Open PowerShell in this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

## Collect
```powershell
python scraper.py PUBLIC_USERNAME --max-posts 100
```
Example:
```powershell
python scraper.py UTDTrey --max-posts 100
```
The browser opens and the collector saves `data/USERNAME_posts.csv`.

## Dashboard
```powershell
streamlit run dashboard.py
```
Open the local URL shown in the terminal, usually http://localhost:8501.

You can also upload a CSV directly. Expected columns: `text`, `created_at`, `likes`, `reposts`, `replies`, `quotes`; optional: `username`, `post_id`, `views`.

## Dashboard features
- Engagement trends and KPI cards
- Likes/reposts scatter plot
- Histograms, box plots, violin plots, correlation heatmap
- Posting weekday/hour heatmap
- VADER sentiment, word cloud, hashtag analysis
- Top posts ranking and downloadable filtered CSV
