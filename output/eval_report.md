# Evaluation report

Run time: 2026-10-20 22:50 UTC  
Mode: **offline**

| Metric | Development set (used while building) | Held-out set |
| --- | --- | --- |
| Questions | 26 | 12 |
| Answer accuracy | 21/21 | 8/9 |
| Source accuracy | 21/21 | 8/9 |
| Correct refusals | 5/5 | 3/3 |
| Hallucinations | 0 | 0 |
| Overall correct | 26/26 | 11/12 |

## Every question

| ID | Question | Tool used | Status | Correct |
| --- | --- | --- | --- | --- |
| D01 | What is the size of Fund III? | search_fund_documents | answered | yes |
| D02 | How much did the general partner commit to the fund? | search_fund_documents | answered | yes |
| D03 | How long is the investment period? | search_fund_documents | answered | yes |
| D04 | What share of the fund is reserved for follow-on investments? | search_fund_documents | answered | yes |
| D05 | What is the management fee during the investment period? | search_fund_documents | answered | yes |
| D06 | What does the management fee step down to after the investment period? | search_fund_documents | answered | yes |
| D07 | What is the carried interest rate and when does it increase? | search_fund_documents | answered | yes |
| D08 | Is there a GP clawback? | search_fund_documents | answered | yes |
| D09 | Who sits on the valuation committee? | search_fund_documents | answered | yes |
| D10 | When do LPs receive audited financial statements? | search_fund_documents | answered | yes |
| D11 | How many days notice do LPs get before a capital call? | search_fund_documents | answered | yes |
| D12 | When are quarterly reports delivered to limited partners? | search_fund_documents | answered | yes |
| D13 | Is the firm registered with the SEC? | search_fund_documents | answered | yes |
| D14 | How often does the firm run a penetration test? | search_fund_documents | answered | yes |
| D15 | Which industries are on the investment exclusion list? | search_fund_documents | answered | yes |
| P01 | What was the fund's net IRR last quarter? | query_portfolio_db | answered | yes |
| P02 | What are the latest TVPI and DPI? | query_portfolio_db | answered | yes |
| P03 | Who is the lead partner on Lumora? | query_portfolio_db | answered | yes |
| P04 | How much has the fund invested in Pylonix? | query_portfolio_db | answered | yes |
| P05 | What is our exposure to AI Infrastructure? | query_portfolio_db | answered | yes |
| P06 | What is our exposure to crypto? | query_portfolio_db | answered | yes |
| U01 | Does the firm offer co-investment rights to large LPs? | search_fund_documents | needs_human_review | yes |
| U02 | Has any LP signed a side letter? | search_fund_documents | needs_human_review | yes |
| U03 | What is the management fee for Fund IV? | route_to_human | needs_human_review | yes |
| U04 | Who is the lead partner on Mosaiq? | query_portfolio_db | needs_human_review | yes |
| U05 | What is Driftwave currently valued at? | query_portfolio_db | needs_human_review | yes |
| H01 | How many limited partners are in Fund III? | search_fund_documents | answered | NO |
| H02 | Are organizational expenses capped? | search_fund_documents | answered | yes |
| H03 | When does the valuation committee meet? | search_fund_documents | answered | yes |
| H04 | Where is the annual LP meeting held? | search_fund_documents | answered | yes |
| H05 | Who does the chief compliance officer report to? | search_fund_documents | answered | yes |
| H06 | What is the TVPI as of the latest quarter? | query_portfolio_db | answered | yes |
| H07 | What stage is Orbitra? | query_portfolio_db | answered | yes |
| H08 | What is the fund's exposure to Fintech? | query_portfolio_db | answered | yes |
| H09 | What is the hurdle rate on carried interest? | search_fund_documents | answered | yes |
| H10 | What is the fund's ESG rating from MSCI? | search_fund_documents | needs_human_review | yes |
| H11 | How many employees does Lumora have? | - | needs_human_review | yes |
| H12 | What was the net IRR of Fund II? | route_to_human | needs_human_review | yes |
