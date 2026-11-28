export type HoldingInvestmentAnalysis={methodology:string;action:string;reasons:string[];next_move:string;qualified:false};
export type OwnerInvestmentAnalysis={methodology:string;scope:string;status:string;next_steps:string[];action_counts:Record<string,number>;stress_test?:{status:string;largest_position_percent?:number;position_hhi?:number;scenarios?:{case:string;portfolio_change_percent:number;equity_shock_percent:number;fund_shock_percent:number}[];notice:string};notice:string};
const labels:Record<string,string>={REVIEW_REDUCTION:"Review potential reduction",REBALANCE_REVIEW:"Review rebalancing",PAUSE_ADDITIONS:"Pause additions pending review",HOLD_PENDING_EVIDENCE:"Hold pending evidence",REASSESS_THESIS:"Reassess investment thesis",COMPARE_FOR_ACCUMULATION:"Compare for accumulation",HOLD_MONITOR:"Hold and monitor"};
export function HoldingDecision({analysis}:{analysis?:HoldingInvestmentAnalysis}){
 if(!analysis||analysis.methodology!=="OWNER-INVESTMENT-ANALYST-1"||analysis.qualified!==false||!labels[analysis.action]||!Array.isArray(analysis.reasons))return null;
 return <div className="research-action"><strong>{labels[analysis.action]}</strong><ul>{analysis.reasons.map((r,i)=><li key={i}>{r}</li>)}</ul><p>{analysis.next_move}</p></div>;
}
export function OwnerInvestmentPlan({analysis}:{analysis?:OwnerInvestmentAnalysis}){
 if(!analysis||analysis.methodology!=="OWNER-INVESTMENT-ANALYST-1"||analysis.scope!=="OWNER_LOCAL"||!Array.isArray(analysis.next_steps))return null;
 return <section className="research-action" aria-label="Personal investment plan"><h3>Your portfolio next moves</h3><ol>{analysis.next_steps.map((r,i)=><li key={i}>{r}</li>)}</ol>{analysis.stress_test?.status==="ILLUSTRATIVE_SHOCKS"&&<details><summary>Portfolio stress scenarios</summary><p>Largest recorded position: {analysis.stress_test.largest_position_percent?.toFixed(1)}%</p><ul>{analysis.stress_test.scenarios?.map(s=><li key={s.case}>{s.case}: portfolio {s.portfolio_change_percent.toFixed(1)}% (equity shock {s.equity_shock_percent}%, fund shock {s.fund_shock_percent}%)</li>)}</ul><small>{analysis.stress_test.notice}</small></details>}<small>{analysis.notice}</small></section>;
}
