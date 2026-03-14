import streamlit as st
import pandas as pd
import numpy_financial as npf

st.set_page_config(page_title="Property Valuation Model", layout="wide")
st.title("🏡 Advanced Property Valuation Model")

# --- SIDEBAR: INPUT PARAMETERS ---
st.sidebar.header("Transaction Assumptions")
purchase_price = st.sidebar.number_input("Purchase Price (R)", value=1880000, step=50000)
renovation_budget = st.sidebar.number_input("Renovation Budget (R)", value=150000, step=10000)
transfer_costs = st.sidebar.number_input("Transfer & Bond Costs (R)", value=65000, step=5000)

st.sidebar.header("Financing")
ltv = st.sidebar.slider("Loan-to-Value (LTV) %", 0, 100, 90) / 100
interest_rate = st.sidebar.number_input("Annual Interest Rate (%)", value=11.75, step=0.25) / 100
loan_term = st.sidebar.number_input("Loan Term (Years)", value=20, step=1)

st.sidebar.header("Operations & Escalations")
monthly_rent = st.sidebar.number_input("Initial Monthly Rent (R)", value=14000, step=500)
rental_escalation = st.sidebar.number_input("Annual Rental Escalation (%)", value=5.0, step=0.5) / 100
monthly_levies_rates = st.sidebar.number_input("Initial Monthly Expenses (R)", value=2500, step=100)
expense_escalation = st.sidebar.number_input("Annual Expense Escalation (%)", value=6.0, step=0.5) / 100
vacancy_rate = st.sidebar.slider("Vacancy Rate (%)", 0, 20, 5) / 100

st.sidebar.header("Exit & Tax Strategy")
holding_period = st.sidebar.slider("Holding Period (Years)", 1, 20, 5)
annual_appreciation = st.sidebar.number_input("Annual Property Appreciation (%)", value=4.0, step=0.5) / 100
marginal_tax_rate = st.sidebar.slider("Marginal Tax Rate for CGT (%)", 18, 45, 45) / 100
discount_rate = st.sidebar.number_input("Target Discount Rate (%)", value=10.0, step=0.5) / 100

# --- CALCULATIONS ---
loan_amount = purchase_price * ltv
total_initial_cash = (purchase_price - loan_amount) + renovation_budget + transfer_costs

# Amortization Schedule Generation
monthly_interest = interest_rate / 12
total_months = loan_term * 12
monthly_bond_payment = npf.pmt(monthly_interest, total_months, -loan_amount) if interest_rate > 0 else loan_amount / total_months
annual_bond_payment = monthly_bond_payment * 12

amortization_data = []
balance = loan_amount
for month in range(1, holding_period * 12 + 1):
    interest_payment = balance * monthly_interest
    principal_payment = monthly_bond_payment - interest_payment
    balance -= principal_payment
    amortization_data.append([month, monthly_bond_payment, principal_payment, interest_payment, balance])

df_amort = pd.DataFrame(amortization_data, columns=['Month', 'Payment', 'Principal', 'Interest', 'Balance'])
df_amort_annual = df_amort.groupby(df_amort['Month'] // 12.01).agg({'Payment':'sum', 'Principal':'sum', 'Interest':'sum', 'Balance':'last'}).reset_index(drop=True)
df_amort_annual.index += 1

# Cash Flow Array & Operations
cash_flows = [-total_initial_cash]
annual_cf_data = []

current_annual_rent = monthly_rent * 12
current_annual_expenses = monthly_levies_rates * 12

for year in range(1, holding_period + 1):
    effective_gross_income = current_annual_rent * (1 - vacancy_rate)
    noi = effective_gross_income - current_annual_expenses
    cf = noi - annual_bond_payment
    
    annual_cf_data.append([year, current_annual_rent, current_annual_expenses, noi, cf])
    
    # Apply escalations for next year
    current_annual_rent *= (1 + rental_escalation)
    current_annual_expenses *= (1 + expense_escalation)
    
    # Exit Calculations in final year
    if year == holding_period:
        exit_value = purchase_price * ((1 + annual_appreciation) ** holding_period)
        remaining_loan = df_amort_annual.iloc[-1]['Balance']
        
        # Capital Gains Tax Calculation (SA Individuals: 40% inclusion rate)
        base_cost = purchase_price + renovation_budget + transfer_costs
        capital_gain = max(0, exit_value - base_cost)
        cgt_liability = capital_gain * 0.40 * marginal_tax_rate
        
        net_proceeds = exit_value - remaining_loan - cgt_liability
        cf += net_proceeds
        
    cash_flows.append(cf)

df_cf = pd.DataFrame(annual_cf_data, columns=['Year', 'Gross Rent', 'Expenses', 'NOI', 'Net Cash Flow'])

# Metrics
irr = npf.irr(cash_flows) * 100 if npf.irr(cash_flows) is not None else 0.0
npv = npf.npv(discount_rate, cash_flows)
cash_on_cash = (df_cf.iloc[0]['Net Cash Flow'] / total_initial_cash) * 100

# --- DASHBOARD UI ---
st.markdown("### Executive Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Initial Cash", f"R {total_initial_cash:,.0f}")
col2.metric("Year 1 Cash-on-Cash", f"{cash_on_cash:.2f} %")
col3.metric("Projected IRR", f"{irr:.2f} %")
col4.metric("Net Present Value", f"R {npv:,.0f}")

st.markdown("---")
st.markdown("### Annual Operating Cash Flow Projection")
st.bar_chart(df_cf.set_index("Year")['Net Cash Flow'])

st.markdown("---")
col_exit, col_amort = st.columns(2)

with col_exit:
    st.markdown("### Exit Strategy & CGT (Year {})".format(holding_period))
    st.write(f"**Gross Sale Price:** R {exit_value:,.0f}")
    st.write(f"**Remaining Bond:** - R {remaining_loan:,.0f}")
    st.write(f"**Capital Gains Tax (CGT):** - R {cgt_liability:,.0f}")
    st.write(f"**Net Equity from Sale:** R {net_proceeds:,.0f}")

with col_amort:
    st.markdown("### Bond Amortization (Annualized)")
    st.dataframe(df_amort_annual.style.format("R {:,.0f}"), use_container_width=True)