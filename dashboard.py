from pathlib import Path
import re
from io import BytesIO

import pandas as pd
import streamlit as st
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="X Analytics", page_icon="𝕏", layout="wide")
st.title("𝕏 Analytics Dashboard")
st.caption("Explore post activity, engagement, timing, hashtags and sentiment.")

def prepare(df):
    df = df.copy()
    if "text" not in df:
        df["text"] = ""
    if "created_at" not in df:
        df["created_at"] = pd.NaT
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    for col in ["likes", "reposts", "replies", "quotes", "views"]:
        if col not in df:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["engagement"] = df[["likes", "reposts", "replies", "quotes"]].sum(axis=1)
    df["hour"] = df["created_at"].dt.hour
    df["weekday"] = df["created_at"].dt.day_name()
    df["hashtags"] = df["text"].fillna("").apply(lambda x: re.findall(r"#(\w+)", x.lower()))
    analyzer = SentimentIntensityAnalyzer()
    df["sentiment_score"] = df["text"].fillna("").apply(lambda x: analyzer.polarity_scores(x)["compound"])
    df["sentiment"] = df["sentiment_score"].apply(
        lambda x: "Positive" if x >= 0.05 else ("Negative" if x <= -0.05 else "Neutral")
    )
    return df

upload = st.file_uploader("Upload a CSV", type=["csv"])
files = sorted(DATA_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
if upload:
    raw = pd.read_csv(BytesIO(upload.getvalue()))
    source = upload.name
elif files:
    selected = st.selectbox("Saved dataset", files, format_func=lambda p: p.name)
    raw = pd.read_csv(selected)
    source = selected.name
else:
    st.info("No dataset yet. Collect posts or upload a CSV.")
    st.code("python scraper.py PUBLIC_USERNAME --max-posts 100")
    st.stop()

df = prepare(raw)
if df.empty:
    st.warning("Dataset is empty.")
    st.stop()

st.caption(f"Dataset: {source} · {len(df)} posts")
with st.sidebar:
    st.header("Filters")
    if "username" in df:
        names = sorted(df["username"].dropna().astype(str).unique())
        chosen = st.multiselect("Username", names, default=names)
        df = df[df["username"].astype(str).isin(chosen)]
    sentiments = st.multiselect("Sentiment", ["Positive", "Neutral", "Negative"],
                                default=["Positive", "Neutral", "Negative"])
    df = df[df["sentiment"].isin(sentiments)]
    valid = df["created_at"].dropna()
    if not valid.empty:
        start, end = st.date_input("Date range", value=(valid.min().date(), valid.max().date()))
        if isinstance(start, object) and isinstance(end, object):
            df = df[df["created_at"].dt.date.between(start, end)]

if df.empty:
    st.warning("No rows match these filters.")
    st.stop()

k = st.columns(5)
for col, label, value in zip(k, ["Posts", "Likes", "Reposts", "Replies", "Total engagement"],
                             [len(df), int(df.likes.sum()), int(df.reposts.sum()),
                              int(df.replies.sum()), int(df.engagement.sum())]):
    col.metric(label, f"{value:,}")

tabs = st.tabs(["Overview", "Statistics", "Time analysis", "NLP & hashtags", "Top posts", "Raw data"])

with tabs[0]:
    a, b = st.columns(2)
    timed = df.dropna(subset=["created_at"]).copy()
    if not timed.empty:
        daily = timed.groupby(timed["created_at"].dt.date).agg(
            Likes=("likes", "sum"), Reposts=("reposts", "sum"), Replies=("replies", "sum")
        ).reset_index(names="Date")
        a.plotly_chart(px.line(daily, x="Date", y=["Likes", "Reposts", "Replies"],
                               markers=True, title="Engagement over time"), use_container_width=True)
    else:
        a.info("No usable timestamps.")
    avg = df[["likes", "reposts", "replies", "quotes"]].mean().rename_axis("Metric").reset_index(name="Average")
    b.plotly_chart(px.bar(avg, x="Metric", y="Average", title="Average engagement per post"), use_container_width=True)
    st.plotly_chart(px.scatter(df, x="likes", y="reposts", size="replies",
                               hover_data=["text"], title="Likes vs reposts (bubble size = replies)"),
                    use_container_width=True)

with tabs[1]:
    a, b = st.columns(2)
    a.plotly_chart(px.histogram(df, x="likes", nbins=30, title="Likes distribution"), use_container_width=True)
    a.plotly_chart(px.box(df, y="engagement", points="outliers", title="Engagement box plot"), use_container_width=True)
    corr = df[["likes", "reposts", "replies", "quotes"]].corr()
    b.plotly_chart(px.imshow(corr, text_auto=".2f", zmin=-1, zmax=1,
                             color_continuous_scale="RdBu_r", title="Engagement correlation"), use_container_width=True)
    b.plotly_chart(px.violin(df, y="likes", box=True, points="outliers", title="Likes violin plot"), use_container_width=True)

with tabs[2]:
    timed = df.dropna(subset=["created_at"]).copy()
    if timed.empty:
        st.info("No usable timestamps.")
    else:
        heat = timed.pivot_table(index="weekday", columns="hour", values="text",
                                 aggfunc="count", fill_value=0)
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heat = heat.reindex([x for x in order if x in heat.index])
        st.plotly_chart(px.imshow(heat, aspect="auto", title="Posting heatmap (weekday × hour)",
                                  labels={"x": "Hour (UTC)", "y": "Weekday", "color": "Posts"}),
                        use_container_width=True)
        daily = timed.groupby(timed["created_at"].dt.date).size().reset_index(name="Posts")
        st.plotly_chart(px.bar(daily, x="created_at", y="Posts", title="Posts per day"), use_container_width=True)

with tabs[3]:
    a, b = st.columns(2)
    sentiment = df["sentiment"].value_counts().rename_axis("Sentiment").reset_index(name="Posts")
    a.plotly_chart(px.pie(sentiment, names="Sentiment", values="Posts", hole=.45,
                          title="Sentiment distribution"), use_container_width=True)
    text = " ".join(df["text"].dropna().astype(str))
    if text.strip():
        cloud = WordCloud(width=1000, height=450, background_color="white",
                          collocations=False).generate(text)
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.imshow(cloud, interpolation="bilinear")
        ax.axis("off")
        a.pyplot(fig)
        plt.close(fig)
    tags = [tag for values in df["hashtags"] for tag in values]
    if tags:
        tag_df = pd.Series(tags).value_counts().head(20).rename_axis("Hashtag").reset_index(name="Count")
        b.plotly_chart(px.bar(tag_df, x="Count", y="Hashtag", orientation="h",
                              title="Top hashtags").update_layout(yaxis={"categoryorder": "total ascending"}),
                        use_container_width=True)
    else:
        b.info("No hashtags found.")
    b.plotly_chart(px.histogram(df, x="sentiment_score", nbins=25,
                                title="Sentiment score distribution"), use_container_width=True)

with tabs[4]:
    top = df.sort_values("engagement", ascending=False).head(20)
    display_cols = [c for c in ["created_at", "text", "likes", "reposts", "replies", "quotes", "engagement"] if c in top]
    st.dataframe(top[display_cols], use_container_width=True, hide_index=True)
    st.plotly_chart(px.bar(top.head(10), x="engagement", y="text", orientation="h",
                           title="Top 10 posts by engagement").update_layout(yaxis={"categoryorder": "total ascending"}),
                    use_container_width=True)

with tabs[5]:
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download filtered CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       "x_analytics_filtered.csv", "text/csv")
