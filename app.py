import streamlit as st
import pandas as pd
import numpy_financial as npf

st.set_page_config(page_title="Property Valuation Model", layout="wide")
st.title("🏡 Advanced Property Valuation Model")

# --- SIDEBAR: INPUT PARAMETERS ---
st.sidebar.header("1. Transaction Assumptions")
purchase_price = st.sidebar.number_input("Purchase Price (R)", value=1880000, step=50000)
renovation_budget = st.sidebar.number_input("Upfront Renovation Budget (R)", value=150000, step=10000)
transfer_costs = st.sidebar.number_input("Transfer & Bond Costs (R)", value=65000, step=5000)

st.sidebar.header("2. Financing")
ltv = st.sidebar.slider("Loan-to-Value (LTV) %", 0, 100, 90) / 100
interest_rate = st.sidebar.number_input("Annual Interest Rate (%)", value=11.75, step=0.25) / 100
loan_term = st.sidebar.number_input("Loan Term (Years)", min_value=1, max_value=30, value=20, step=1)

st.sidebar.header("3. Monthly Operations")
monthly_rent = st.sidebar.number_input("Rental Income (R)", value=14000, step=500)
rates_taxes = st.sidebar.number_input("Rates & Taxes (R)", value=1200, step=100)
water = st.sidebar.number_input("Water (R)", value=300, step=50)
electricity = st.sidebar.number_input("Electricity (R)", value=800, step=50)
levies = st.sidebar.number_input("Standard Levies (R)", value=1500, step=100)
special_levies = st.sidebar.number_input("Special Levies (R)", value=0, step=100)
vacancy_rate = st.sidebar.slider("Vacancy Rate (%)", 0, 20, 5) / 100

st.sidebar.header("4. Escalations & Strategy")
rental_escalation = st.sidebar.number_input("Annual Rental Escalation (%)", value=5.0, step=0.5) / 100
expense_escalation = st.sidebar.number_input("Annual Expense Escalation (%)", value=6.0, step=0.5) / 100
# Holding period is dynamically capped by the loan term
holding_period = st.sidebar.slider("Holding Period (Years)", min_value=1, max_value=int(loan_term), value=min(5, int(loan_term)))
annual_appreciation = st.sidebar.number_input("Annual Property Appreciation (%)", value=4.0, step=0.5) / 100
discount_rate = st.sidebar.number_input("Target Discount Rate (%)", value=10.0, step=0.5) / 100

# --- CALCULATIONS ---
loan_amount = purchase_price * ltv
total_initial_cash = (purchase_price - loan_amount) + renovation_budget + transfer_costs

# Amortization Schedule Generation (Monthly & Annual)
monthly_interest = interest_rate / 12
total_months = loan_term * 12
monthly_bond_payment = npf.pmt(monthly_interest, total_months, -loan_amount) if interest_rate > 0 else loan_amount / total_months
annual_bond_payment = monthly_bond_payment * 12

amortization_data = []
balance = loan_amount
for month in range(1, total_months + 1):
    interest_payment = balance * monthly_interest
    principal_payment = monthly_bond_payment - interest_payment
    balance -= principal_payment
    amortization_data.append([month, monthly_bond_payment, principal_payment, interest_payment, max(0, balance)])

df_amort_monthly = pd.DataFrame(amortization_data, columns=['Month', 'Payment', 'Principal', 'Interest', 'Balance'])

# Group by year for the annual view
df_amort_annual = df_amort_monthly.copy()
df_amort_annual['Year'] = ((df_amort_annual['Month'] - 1) // 12) + 1
df_amort_annual = df_amort_annual.groupby('Year').agg({
    'Payment': 'sum', 
    'Principal': 'sum', 
    'Interest': 'sum', 
    'Balance': 'last'
}).reset_index()

# Cash Flow Array & Operations
cash_flows = [-total_initial_cash]
detailed_cf_data = []

current_rent = monthly_rent * 12
current_rates = rates_taxes * 12
current_water = water * 12
current_elec = electricity * 12
current_levies = levies * 12
current_special = special_levies * 12

for year in range(1, holding_period + 1):
    effective_gross_income = current_rent * (1 - vacancy_rate)
    total_expenses = current_rates + current_water + current_elec + current_levies + current_special
    noi = effective_gross_income - total_expenses
    cf = noi - annual_bond_payment
    
    detailed_cf_data.append([
        year, effective_gross_income, current_rates, current_water, 
        current_elec, current_levies, current_special, total_expenses, 
        noi, annual_bond_payment, cf
    ])
    
    # Apply escalations for next year
    current_rent *= (1 + rental_escalation)
    current_rates *= (1 + expense_escalation)
    current_water *= (1 + expense_escalation)
    current_elec *= (1 + expense_escalation)
    current_levies *= (1 + expense_escalation)
    current_special *= (1 + expense_escalation) # Assuming special levies escalate, adjust if fixed
    
    # Exit Calculations in final year
    if year == holding_period:
        exit_value = purchase_price * ((1 + annual_appreciation) ** holding_period)
        remaining_loan = df_amort_annual[df_amort_annual['Year'] == holding_period]['Balance'].values[0]
        net_proceeds = exit_value - remaining_loan
        cf += net_proceeds
        
    cash_flows.append(cf)

df_cf = pd.DataFrame(detailed_cf_data, columns=[
    'Year', 'Effective Rent', 'Rates & Taxes', 'Water', 'Electricity', 
    'Standard Levies', 'Special Levies', 'Total Opex', 'NOI', 'Bond Payment', 'Net Cash Flow'
])

# Metrics
irr = npf.irr(cash_flows) * 100 if npf.irr(cash_flows) is not None else 0.0
npv = npf.npv(discount_rate, cash_flows)
cash_on_cash = (df_cf.iloc[0]['Net Cash Flow'] / total_initial_cash) * 100

# --- DASHBOARD UI ---
st.markdown("### Executive Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Initial Cash (Inc. Renovations)", f"R {total_initial_cash:,.0f}")
col2.metric("Year 1 Cash-on-Cash", f"{cash_on_cash:.2f} %")
col3.metric("Projected IRR", f"{irr:.2f} %")
col4.metric("Net Present Value", f"R {npv:,.0f}")

st.markdown("---")

# Use Tabs to organize the dense information cleanly
tab1, tab2, tab3 = st.tabs(["📊 Projected Cash Flows", "📉 Amortization Schedule", "🚪 Exit Strategy"])

with tab1:
    st.markdown("### Detailed Annual Cash Flow Projection")
    st.dataframe(df_cf.style.format("R {:,.0f}"), use_container_width=True)
    st.bar_chart(df_cf.set_index("Year")['Net Cash Flow'])

with tab2:
    st.markdown("### Bond Amortization Schedule")
    view_type = st.radio("Select View:", ["Annual View", "Monthly View"], horizontal=True)
    
    if view_type == "Annual View":
        # Only show up to the holding period for relevance, or full loan term if desired
        st.dataframe(df_amort_annual.head(holding_period).style.format("R {:,.0f}"), use_container_width=True)
    else:
        # Show monthly breakdown up to the holding period
        months_to_show = holding_period * 12
        st.dataframe(df_amort_monthly.head(months_to_show).style.format("R {:,.0f}"), use_container_width=True)

with tab3:
    st.markdown("### Exit Strategy (Year {})".format(holding_period))
    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**Gross Sale Price:** R {exit_value:,.0f}")
        st.write(f"**Remaining Bond Balance:** - R {remaining_loan:,.0f}")
        st.markdown("---")
        st.write(f"**Net Equity from Sale:** R {net_proceeds:,.0f}")
    with col_b:
        st.info("Note: This simple exit calculation does not include Capital Gains Tax (CGT) or agent commissions upon sale.")
