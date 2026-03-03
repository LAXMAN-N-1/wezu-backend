import streamlit as st
import asyncio
import pandas as pd

# Import the new services directly to bypass JWT Auth for quick testing
from app.services.analytics.admin_service import analytics_admin_service
from app.services.analytics.dealer_service import analytics_dealer_service
from app.services.analytics.logistics_service import analytics_logistics_service
from app.services.analytics.customer_service import analytics_customer_service

st.set_page_config(page_title="Wezu Analytics Test", layout="wide")

st.title("🔋 Wezu Story-Driven Analytics (Mock V2 Test)")
st.markdown("This dashboard directly fetches data from the new scalable `app/services/analytics/` architecture to visualize the Pydantic DTO responses.")

# Helper to run async service methods
def fetch_mock_data(service_method):
    return asyncio.run(service_method(db=None))

# Sidebar to switch personas
persona = st.sidebar.radio("Select App Persona", ["Super Admin (Hawk-Eye)", "Dealer (P&L)", "Logistics (Runner)", "Customer (Rider)"])

def render_kpi(col, title, kpi_card):
    delta_color = "normal"
    if kpi_card.status == "down":
        delta_color = "inverse"
        
    col.metric(
        label=title,
        value=f"{kpi_card.value:,.0f}",
        delta=f"{kpi_card.trend_percentage}%",
        delta_color=delta_color
    )

if persona == "Super Admin (Hawk-Eye)":
    st.header("🦅 Admin: Growth & Risk")
    data = fetch_mock_data(analytics_admin_service.get_overview)
    
    # Row 1: KPIs
    cols = st.columns(3)
    render_kpi(cols[0], "Monthly Recurring Revenue", data.overview["mrr"])
    render_kpi(cols[1], "Net Revenue", data.overview["revenue"])
    cols[2].metric("Critical System Alerts", data.risk["critical_alerts"], "-1", delta_color="inverse")
    
    st.divider()
    # Row 2: Financial Trend (Simulating Flutter Line Chart)
    st.subheader("Financial Trend (Domain DTO)")
    df = pd.DataFrame([point.dict() for point in data.financials["monthly_trend"]])
    if not df.empty:
        df.set_index("x", inplace=True)
        st.line_chart(df)
        
    st.write("Raw JSON API Contract payload:", data.dict())

elif persona == "Dealer (P&L)":
    st.header("🏪 Dealer: P&L & Inventory Manager")
    data = fetch_mock_data(analytics_dealer_service.get_overview)
    
    cols = st.columns(3)
    render_kpi(cols[0], "Walk-in Conversion %", data.overview["conversion"])
    cols[1].metric("Days of Charge Inventory", data.inventory["days_of_charge"], "-1 Day")
    
    st.write("Raw JSON API Contract payload:", data.dict())

elif persona == "Logistics (Runner)":
    st.header("🚚 Logistics: Live Network Operations")
    data = fetch_mock_data(analytics_logistics_service.get_overview)
    
    cols = st.columns(3)
    render_kpi(cols[0], "Mean Time To Rescue (mins)", data.overview["mttr"])
    
    st.write("Raw JSON API Contract payload:", data.dict())

elif persona == "Customer (Rider)":
    st.header("🏍️ Customer: Rider Dashboard")
    data = fetch_mock_data(analytics_customer_service.get_overview)
    
    cols = st.columns(4)
    cols[0].metric("Current Range (km)", data.ride_status["current_range"])
    cols[1].metric("Battery Health", data.ride_status["battery_health"].title())
    cols[2].metric("Eco-Score", data.gamification["eco_score"], "Top 10%")
    render_kpi(cols[3], "Money Saved vs Petrol (₹)", data.savings["money_saved"])
    
    st.write("Raw JSON API Contract payload:", data.dict())
