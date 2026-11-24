export type Article={id:string;headline:string;url:string;published_at:string;topics:string[];sentiment:string;source_provider:string};
export type NewsEvidence={status:string;retrieved_at:string;articles:Article[];notice:string};
const words=(s:string)=>s.toLowerCase().replace(/_/g," ");
function Articles({articles}:{articles:Article[]}){
 return <div className="p1-news">{articles.map(article=><a href={article.url} key={article.id} target="_blank" rel="noopener noreferrer"><small>{new Date(article.published_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST · Upstox News</small><strong>{article.headline}</strong><small>{article.topics.length?"Review topics: "+article.topics.map(words).join(" · "):"No topic match"} · Sentiment not analyzed</small></a>)}</div>;
}
export default function AutomaticCompanyNews({evidence,status}:{evidence?:NewsEvidence;status?:string}){
 if(!evidence)return <p className="muted tiny">{status==="ENABLED"?"Recent company news awaiting usable provider evidence.":"Automatic news unavailable or not authorized."}</p>;
 return <details><summary>Recent company news ({evidence.articles.length})</summary>
 {evidence.articles.length?<Articles articles={evidence.articles}/>:<p>{words(evidence.status)}. No absence-of-risk claim.</p>}
 <p className="muted tiny">{evidence.notice}</p></details>;
}
export function RecentCompanyNews({articles}:{articles:Article[]}){
 return <section className="panel glass" aria-label="Automatic company news"><div className="sectionhead"><div><small className="section-kicker">NEWS &amp; EVENT RESEARCH</small><h3>Recent watched-company news</h3><p className="muted tiny">Source-linked headlines · selected candidates only · not global coverage</p></div></div><Articles articles={articles}/><p className="muted tiny">Topic matches flag items for review. Sentiment, claims and impact are not independently verified.</p></section>;
}
