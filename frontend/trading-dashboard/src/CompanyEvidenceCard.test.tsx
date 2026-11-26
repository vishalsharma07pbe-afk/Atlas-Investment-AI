/** @vitest-environment jsdom */
import {afterEach,expect,it} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import CompanyEvidenceCard,{type CompanyEvidence} from "./CompanyEvidenceCard";
afterEach(cleanup);
it("shows dated provider ratios and explicitly missing financial sections",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:{status:"AVAILABLE",data:[{name:"P/E",company_value:20,sector_value:10,unit:"RATIO"}],source:null},income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("P/E")).toBeTruthy();
 expect(screen.getByText("20")).toBeTruthy();
 expect(screen.getByText("10")).toBeTruthy();
 expect(screen.getByText(/No fair-value estimate/)).toBeTruthy();
});

it("shows comparable fundamentals and valuation without claiming fair value",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:missing,income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing},fundamental_quality:{
 status:"REVIEW_REQUIRED",strengths:[],warnings:["NET_MARGIN_DETERIORATION_REVIEW"],
 multi_year_quality:{status:"REPORTED_MULTI_YEAR_EVIDENCE",metrics:[{metric:"NET_PROFIT",unit:"INR crore",observations:[{period:"2023-03",value:10},{period:"2024-03",value:20},{period:"2025-03",value:30},{period:"2026-03",value:40}],increasing_years:3,decreasing_years:0,unchanged_years:0,nonpositive_years:0}],cash_conversion:{first_period:"2023-03",last_period:"2026-03",cumulative_operating_cash:40,cumulative_net_profit:100,unit:"INR crore",cash_to_profit_ratio:0.4,negative_cash_years:1},missing_metrics:[],notice:"Reported observations, not a forecast."},
 derived_metrics:[{metric:"NET_MARGIN",previous_year:2024,latest_year:2025,previous_value:20,latest_value:15,change:-5,unit:"PERCENT"}],
 sector_comparisons:[{metric:"PE",company:20,sector:10,unit:"RATIO",difference:10,premium_discount_percent:100,position:"ABOVE_SECTOR"}],
 valuation:{status:"SECTOR_COMPARISON_ONLY",fair_value:null,scenario_status:"DATED_VALUATION_INPUTS_REQUIRED"},gaps:["RATIO_OBSERVATION_PERIOD_UNVERIFIED"],notice:"Comparisons only."}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("Reported deterioration requires review")).toBeTruthy();
 expect(screen.getByText("100% premium")).toBeTruthy();
 expect(screen.getByText("3 up / 0 down / 0 flat")).toBeTruthy();
 expect(screen.getByText("0.4x")).toBeTruthy();
 expect(screen.getByText("FY2025: 15%")).toBeTruthy();
 expect(screen.getByText(/Fair value and valuation scenarios withheld/)).toBeTruthy();
});

it("renders bounded peer comparisons without implying sector leadership",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:missing,income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing},peer_research:{
 status:"SAMPLED_PEER_COMPARISON",selected_peer_count:3,cached_same_sector_count:3,minimum_peers_per_metric:3,sample_limit:3,
 valuation_research:{status:"UNDATED_PEER_MULTIPLES",same_industry_cached_count:3,metrics:[{metric:"PE",company_value:8,peer_median:20,peer_min:10,peer_max:30,peer_count:3,premium_discount_percent:-60,company_retrieved_at:"2026-11-25T10:00:00Z",observation_period:"UNVERIFIED",peers:[]}],review_prompt:"DISCOUNT_WITH_REPORTED_DETERIORATION_REVIEW",notice:"Not matched valuation dates."},
 metrics:[{metric:"REVENUE",period:"2026-03",unit:"INR_CRORE",company_value:100,peer_median:120,peer_count:3,peers_above:2,peers_below:1,peers:[]}],
 notice:"Sample only; not market share."}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("2 above · 1 below · 3 peers")).toBeTruthy();
 expect(screen.getByText("120 Cr")).toBeTruthy();
 expect(screen.getByText("60% discount")).toBeTruthy();
 expect(screen.getByText(/discount coincides with reported financial deterioration/)).toBeTruthy();
 expect(screen.getByText("Sample only; not market share.")).toBeTruthy();
});

it("shows reported quarterly ownership changes without treating them as trades",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:missing,income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing},
 ownership_research:{status:"COMPARABLE_QUARTERS",latest_period:"2026-09-30",previous_period:"2026-06-30",
 categories:[{category:"promoters",latest_percent:48,previous_percent:50,change_pp:-2}],
 review_prompts:[{category:"promoters",change_pp:-2,reason:"REPORTED_OWNERSHIP_DECLINE_AT_LEAST_ONE_PP"}],
 notice:"Quarterly ownership changes are not proof of buying or selling.",blockers:["PROMOTER_PLEDGE_DATA_UNVERIFIED"]}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("48%")).toBeTruthy();
 expect(screen.getByText("-2 pp")).toBeTruthy();
 expect(screen.getByText(/Review reported declines/)).toBeTruthy();
 expect(screen.getByText(/not proof of buying or selling/)).toBeTruthy();
});

it("shows annual cash and liquidity evidence without imputing free cash flow",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:missing,income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing},
 financial_strength:{status:"REPORTED_ANNUAL_FINANCIAL_STRENGTH",unit:"INR_CRORE",liquidity:[{period:"2026-03",current_assets:120,current_liabilities:100,current_ratio:1.2,working_capital:20,reported_net_current_asset:null,net_current_asset_difference:null}],cash_flows:[{period:"2026-03",operating:60,investing:-50,financing:-8,combined_cash_flows:2,reported_total_cash_flow:null,total_cash_flow_difference:null,opening_cash:null,closing_cash:null,cash_balance_movement:null,balance_movement_difference:null}],notice:"Investing cash flow is not capital expenditure."}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("1.2x")).toBeTruthy();
 expect(screen.getByText("Liquidity and cash flow reconciliation")).toBeTruthy();
 expect(screen.getByText("Investing cash flow is not capital expenditure.")).toBeTruthy();
});

it("separates older detailed earnings from current summary and withholds valuation",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:missing,income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing},
 earnings_quality:{status:"REPORTED_EARNINGS_BRIDGES",latest_summary_period:"2026-03",latest_detail_period:"2025-03",period_scope_status:"DETAIL_OLDER_THAN_SUMMARY",revenue_bridge:[],pretax_bridge:[],tax_bridge:[{period:"2025-03",profit_before_tax:30,tax:8,profit_after_tax:22,reported_tax_to_pretax_percent:26.6667,reconciliation_difference:0}],cash_quality:[],valuation_blockers:["VERIFIED_SHARE_AND_EPS_BASIS_REQUIRED"],notice:"No target price or intrinsic value."}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText(/Detailed earnings statement is older/)).toBeTruthy();
 expect(screen.getByText("26.67%")).toBeTruthy();
 expect(screen.getByText("verified share and eps basis required")).toBeTruthy();
});
