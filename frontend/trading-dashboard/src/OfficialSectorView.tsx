type Window={stock_return_percent:number;index_return_percent:number;difference_pp:number;first_date:string;last_date:string};
export type OfficialSectorEvidence={benchmark_key:string;exchange:string;id:number;as_of:string;windows:Record<string,Window>;notice:string};
const fmt=(n:number)=>n.toLocaleString("en-IN",{maximumFractionDigits:2});
export default function OfficialSectorView({report}:{report:OfficialSectorEvidence}){
 return <details><summary>Official sector price index · {report.benchmark_key.replace("NSE_INDEX|","")}</summary>
 <p>Matched NSE session observations through {report.as_of}</p><div className="tablewrap"><table><thead><tr><th>Returns</th><th>Stock</th><th>Index</th><th>Difference</th></tr></thead><tbody>{["20","60","120","252"].filter(n=>report.windows[n]).map(n=>{const w=report.windows[n];return <tr key={n}><td>{n} <small>{w.first_date} – {w.last_date}</small></td><td>{fmt(w.stock_return_percent)}%</td><td>{fmt(w.index_return_percent)}%</td><td>{w.difference_pp>0?"+":""}{fmt(w.difference_pp)} pp</td></tr>})}</tbody></table></div><p className="muted tiny">{report.notice}</p></details>;
}
