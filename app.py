import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="NYPD Complaints Dashboard", layout="wide")

@st.cache_data
def LoadComplaintDf(UploadedFile, LocalPath):
    if UploadedFile is not None:
        ComplaintDf = pd.read_csv(UploadedFile, low_memory=False)
    else:
        ComplaintDf = pd.read_csv(LocalPath, low_memory=False)

    if "CMPLNT_FR_DT" in ComplaintDf.columns:
        ComplaintDf["CMPLNT_FR_DT"] = pd.to_datetime(ComplaintDf["CMPLNT_FR_DT"], errors="coerce")

    if "CMPLNT_FR_TM" in ComplaintDf.columns and "Hour" not in ComplaintDf.columns:
        ComplaintDf["Hour"] = pd.to_datetime(ComplaintDf["CMPLNT_FR_TM"].astype(str), errors="coerce").dt.hour

    if "CMPLNT_FR_DT" in ComplaintDf.columns:
        ComplaintDf["Year"] = ComplaintDf["CMPLNT_FR_DT"].dt.year
        ComplaintDf["MonthNum"] = ComplaintDf["CMPLNT_FR_DT"].dt.month
        ComplaintDf["MonthName"] = ComplaintDf["CMPLNT_FR_DT"].dt.strftime("%b")
        ComplaintDf["DayOfWeek"] = ComplaintDf["CMPLNT_FR_DT"].dt.day_name()

        CurrentYear = pd.Timestamp.today().year
        ComplaintDf = ComplaintDf[ComplaintDf["Year"].between(2005, CurrentYear)]

    if "BORO_NM" in ComplaintDf.columns:
        ComplaintDf = ComplaintDf.dropna(subset=["BORO_NM"])

    return ComplaintDf

st.title("NYPD Complaints (Sample) — EDA Dashboard")

UploadedFile = st.file_uploader("Upload CSV (optional)", type=["csv"])
LocalPath = st.text_input("Or enter local CSV path", value="")

if UploadedFile is None and LocalPath.strip() == "":
    st.stop()

ComplaintDf = LoadComplaintDf(UploadedFile, LocalPath)

LawFilterDefault = ["FELONY", "MISDEMEANOR"] if "LAW_CAT_CD" in ComplaintDf.columns else []
BoroughDefault = sorted(ComplaintDf["BORO_NM"].dropna().unique().tolist()) if "BORO_NM" in ComplaintDf.columns else []

with st.sidebar:
    st.header("Filters")
    if "LAW_CAT_CD" in ComplaintDf.columns:
        LawCats = sorted(ComplaintDf["LAW_CAT_CD"].dropna().unique().tolist())
        LawFilter = st.multiselect("LAW_CAT_CD", LawCats, default=[c for c in LawFilterDefault if c in LawCats])
    else:
        LawFilter = []

    if "BORO_NM" in ComplaintDf.columns:
        Boroughs = sorted(ComplaintDf["BORO_NM"].dropna().unique().tolist())
        BoroughFilter = st.multiselect("BORO_NM", Boroughs, default=BoroughDefault)
    else:
        BoroughFilter = []

    MaxRows = st.slider("Max rows for map (sampling)", 5_000, 200_000, 50_000, step=5_000)

FilteredDf = ComplaintDf.copy()

if "LAW_CAT_CD" in FilteredDf.columns and len(LawFilter) > 0:
    FilteredDf = FilteredDf[FilteredDf["LAW_CAT_CD"].isin(LawFilter)]

if "BORO_NM" in FilteredDf.columns and len(BoroughFilter) > 0:
    FilteredDf = FilteredDf[FilteredDf["BORO_NM"].isin(BoroughFilter)]

Tab1, Tab2, Tab3 = st.tabs(["Counts & Trends", "Composition", "Map"])

with Tab1:
    ColA, ColB = st.columns(2)

    with ColA:
        if "BORO_NM" in FilteredDf.columns:
            BoroughTotalsDf = (
                FilteredDf["BORO_NM"]
                .dropna()
                .value_counts()
                .rename_axis("Borough")
                .reset_index(name="ComplaintCount")
            )
            FigBorough = px.bar(BoroughTotalsDf, x="Borough", y="ComplaintCount",
                                title="Total NYPD Complaints by Borough")
            st.plotly_chart(FigBorough, use_container_width=True)

    with ColB:
        if {"Year", "LAW_CAT_CD"}.issubset(FilteredDf.columns):
            YearLawDf = (
                FilteredDf.dropna(subset=["Year", "LAW_CAT_CD"])
                .groupby(["Year", "LAW_CAT_CD"])
                .size()
                .reset_index(name="ComplaintCount")
                .sort_values("Year")
            )
            FigYearLaw = px.line(YearLawDf, x="Year", y="ComplaintCount", color="LAW_CAT_CD",
                                 markers=True, title="Yearly Complaint Counts by Law Category")
            st.plotly_chart(FigYearLaw, use_container_width=True)

    if {"Year", "BORO_NM", "LAW_CAT_CD"}.issubset(FilteredDf.columns):
        YearBoroLawDf = (
            FilteredDf.dropna(subset=["Year", "BORO_NM", "LAW_CAT_CD"])
            .groupby(["BORO_NM", "Year", "LAW_CAT_CD"])
            .size()
            .reset_index(name="ComplaintCount")
            .sort_values(["BORO_NM", "Year"])
        )
        FigFacet = px.line(
            YearBoroLawDf,
            x="Year",
            y="ComplaintCount",
            color="LAW_CAT_CD",
            facet_col="BORO_NM",
            facet_col_wrap=3,
            markers=True,
            title="Yearly Complaint Counts by Borough and Law Category"
        )
        st.plotly_chart(FigFacet, use_container_width=True)

with Tab2:
    ColC, ColD = st.columns(2)

    with ColC:
        if {"BORO_NM", "Year", "LAW_CAT_CD"}.issubset(FilteredDf.columns):
            HeatBaseDf = (
                FilteredDf.dropna(subset=["BORO_NM", "Year", "LAW_CAT_CD"])
                .groupby(["BORO_NM", "Year", "LAW_CAT_CD"])
                .size()
                .reset_index(name="Count")
            )
            FelonyDf = HeatBaseDf[HeatBaseDf["LAW_CAT_CD"] == "FELONY"][["BORO_NM", "Year", "Count"]].rename(columns={"Count": "FelonyCount"})
            TotalDf = HeatBaseDf.groupby(["BORO_NM", "Year"])["Count"].sum().reset_index(name="TotalCount")
            FelonyShareDf = FelonyDf.merge(TotalDf, on=["BORO_NM", "Year"], how="right").fillna({"FelonyCount": 0})
            FelonyShareDf["FelonyShare"] = FelonyShareDf["FelonyCount"] / FelonyShareDf["TotalCount"].replace(0, np.nan)

            YearBinSize = st.selectbox("Heatmap year bin", [1, 5], index=1)
            if YearBinSize == 5:
                FelonyShareDf["YearBin"] = (FelonyShareDf["Year"] // 5) * 5
                HeatAggDf = FelonyShareDf.groupby(["BORO_NM", "YearBin"])["FelonyShare"].mean().reset_index()
                HeatPivotDf = HeatAggDf.pivot(index="BORO_NM", columns="YearBin", values="FelonyShare")
                FigHeat = px.imshow(HeatPivotDf, aspect="auto", title="Felony Share by Borough and Year (binned)")
            else:
                HeatPivotDf = FelonyShareDf.pivot(index="BORO_NM", columns="Year", values="FelonyShare")
                FigHeat = px.imshow(HeatPivotDf, aspect="auto", title="Felony Share by Borough and Year")
            st.plotly_chart(FigHeat, use_container_width=True)

    with ColD:
        if {"MonthNum", "MonthName", "LAW_CAT_CD"}.issubset(FilteredDf.columns):
            MonthDf = (
                FilteredDf.dropna(subset=["MonthNum", "MonthName", "LAW_CAT_CD"])
                .groupby(["MonthNum", "MonthName", "LAW_CAT_CD"])
                .size()
                .reset_index(name="ComplaintCount")
                .sort_values("MonthNum")
            )
            FigMonth = px.line(MonthDf, x="MonthName", y="ComplaintCount", color="LAW_CAT_CD",
                               markers=True, category_orders={"MonthName": MonthDf["MonthName"].tolist()},
                               title="Monthly Pattern of NYPD Complaints by Law Category")
            st.plotly_chart(FigMonth, use_container_width=True)

    ColE, ColF = st.columns(2)

    with ColE:
        if {"DayOfWeek", "LAW_CAT_CD"}.issubset(FilteredDf.columns):
            DayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            DayDf = (
                FilteredDf.dropna(subset=["DayOfWeek", "LAW_CAT_CD"])
                .groupby(["DayOfWeek", "LAW_CAT_CD"])
                .size()
                .reset_index(name="ComplaintCount")
            )
            FigDay = px.line(DayDf, x="DayOfWeek", y="ComplaintCount", color="LAW_CAT_CD",
                             markers=True, category_orders={"DayOfWeek": DayOrder},
                             title="Day-of-Week Pattern by Law Category")
            st.plotly_chart(FigDay, use_container_width=True)

    with ColF:
        if {"Hour", "LAW_CAT_CD"}.issubset(FilteredDf.columns):
            HourDf = (
                FilteredDf.dropna(subset=["Hour", "LAW_CAT_CD"])
                .groupby(["Hour", "LAW_CAT_CD"])
                .size()
                .reset_index(name="ComplaintCount")
                .sort_values("Hour")
            )
            FigHour = px.line(HourDf, x="Hour", y="ComplaintCount", color="LAW_CAT_CD",
                              markers=True, title="Hourly Pattern by Law Category")
            st.plotly_chart(FigHour, use_container_width=True)

    if {"OFNS_DESC", "LAW_CAT_CD"}.issubset(FilteredDf.columns):
        TopK = st.slider("Top offenses", 5, 30, 15, step=1)

        TmpDf = FilteredDf[["OFNS_DESC", "LAW_CAT_CD"]].copy()
        TmpDf["OFNS_DESC"] = TmpDf["OFNS_DESC"].astype("string").str.strip().replace("", pd.NA)
        TmpDf = TmpDf.dropna(subset=["OFNS_DESC", "LAW_CAT_CD"])

        TopOffenses = TmpDf["OFNS_DESC"].value_counts().head(TopK).index

        CountsDf = (
            TmpDf[TmpDf["OFNS_DESC"].isin(TopOffenses)]
            .groupby(["OFNS_DESC", "LAW_CAT_CD"])
            .size()
            .reset_index(name="Count")
        )

        TotalDf = CountsDf.groupby("OFNS_DESC")["Count"].sum().reset_index(name="ComplaintCount")

        DominantDf = (
            CountsDf.sort_values(["OFNS_DESC", "Count"], ascending=[True, False])
            .drop_duplicates("OFNS_DESC")
            .rename(columns={"LAW_CAT_CD": "DominantLawCat"})
            [["OFNS_DESC", "DominantLawCat"]]
        )

        TopOffensesDf = (
            TotalDf.merge(DominantDf, on="OFNS_DESC", how="left")
            .rename(columns={"OFNS_DESC": "Offense"})
            .sort_values("ComplaintCount", ascending=False)
        )

        FigTopOffenses = px.bar(
            TopOffensesDf,
            x="ComplaintCount",
            y="Offense",
            orientation="h",
            color="DominantLawCat",
            color_discrete_map={"MISDEMEANOR": "red", "FELONY": "blue"},
            title="Top Offenses (colored by dominant law category)"
        )
        FigTopOffenses.update_yaxes(autorange="reversed")
        st.plotly_chart(FigTopOffenses, use_container_width=True)

with Tab3:
    if {"Latitude", "Longitude"}.issubset(FilteredDf.columns):
        MapDf = FilteredDf.dropna(subset=["Latitude", "Longitude"]).copy()
        if len(MapDf) > MaxRows:
            MapDf = MapDf.sample(MaxRows, random_state=42)

        FigMap = px.scatter_mapbox(
            MapDf,
            lat="Latitude",
            lon="Longitude",
            zoom=9,
            opacity=0.4,
            title="Complaint Locations (sampled)"
        )
        FigMap.update_layout(mapbox_style="open-street-map")
        st.plotly_chart(FigMap, use_container_width=True)
    else:
        st.info("Latitude/Longitude not available; skipping map.")
