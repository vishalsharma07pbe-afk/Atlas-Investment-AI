export type BenchmarkRisk={
  status:string;matchedWeeks?:number;from?:string|null;through?:string|null;
  portfolioReturnPercent?:number|null;benchmarkReturnPercent?:number|null;
  relativePercentagePoints?:number|null;beta?:number|null;
  annualizedTrackingErrorPercent?:number|null;informationRatio?:number|null;attentionStatus:string;
};

const fixed=(value:number|null|undefined,suffix="")=>value==null||!Number.isFinite(value)?"Unavailable":value.toFixed(2)+suffix;

export default function PortfolioBenchmarkRisk({report,compact=false}:{report:BenchmarkRisk;compact?:boolean}){
  const available=report.status==="AVAILABLE_PRICE_REFERENCE_ESTIMATE";
  return <section className={compact?"doctor-item":"portfolio-benchmark-risk"} aria-label="Portfolio relative risk">
    <h3>Relative performance &amp; risk</h3>
    <p>{report.attentionStatus==="REVIEW_RELATIVE_LAG"?"Review: recorded portfolio lagged the NIFTY 50 price reference by at least 5 percentage points.":available?"No relative-lag threshold triggered.":"Comparable portfolio and index evidence is insufficient."}</p>
    {available&&<div className={compact?"doctor-stats":"portfolio-history-metrics"}>
      <div><span>13-week portfolio estimate</span><strong>{fixed(report.portfolioReturnPercent,"%")}</strong></div>
      <div><span>NIFTY 50 price return</span><strong>{fixed(report.benchmarkReturnPercent,"%")}</strong></div>
      <div><span>Relative difference</span><strong>{fixed(report.relativePercentagePoints," pp")}</strong></div>
      {!compact&&<><div><span>Historical beta</span><strong>{fixed(report.beta)}</strong></div>
      <div><span>Annualized tracking error</span><strong>{fixed(report.annualizedTrackingErrorPercent,"%")}</strong></div>
      <div><span>Historical information ratio</span><strong>{fixed(report.informationRatio)}</strong></div></>}
    </div>}
    <p className="muted tiny">{report.matchedWeeks??0}/13 matched weekly intervals{report.from&&report.through?` · ${report.from} to ${report.through}`:""}. Price-only equity reference, not a personalized total-return benchmark. Recorded holdings and cash-flow estimates may be incomplete. Review flag is not a buy or sell signal.</p>
  </section>;
}
