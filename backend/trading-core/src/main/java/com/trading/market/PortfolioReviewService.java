package com.trading.market;

import java.math.*;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Local, deterministic holding-level review. Never sends holdings to an AI or provider. */
@Service
public class PortfolioReviewService {
  private final JdbcTemplate jdbc;
  private final com.fasterxml.jackson.databind.ObjectMapper json;
  private final PortfolioThesisService thesis;
  public PortfolioReviewService(JdbcTemplate jdbc,com.fasterxml.jackson.databind.ObjectMapper json,PortfolioThesisService thesis){
    this.jdbc=jdbc;this.json=json;this.thesis=thesis;
  }

  private String revision(UUID owner){
    return jdbc.queryForObject("""
      SELECT md5(coalesce(string_agg(id::text||':'||updated_at::text,',' ORDER BY id),''))
      FROM personal_holdings WHERE user_id=?
      """,String.class,owner);
  }

  // Journal records are insert/delete only. Keep this revision separate from
  // the holdings hash used by the existing risk notification pipeline.
  private String journalRevision(UUID owner){
    return jdbc.queryForObject("""
      SELECT md5(coalesce(string_agg(id::text,',' ORDER BY id),''))
      FROM (SELECT id FROM portfolio_transactions WHERE user_id=?
        AND transaction_type IN ('BUY','SELL') ORDER BY id LIMIT 5001) journal
      """,String.class,owner);
  }

  public Map<String,Object> current(UUID owner){
    String revision=revision(owner);
    var cached=jdbc.queryForList("""
      SELECT result::text FROM portfolio_review_snapshots WHERE user_id=?
        AND holdings_revision=? AND generated_at>=now()-interval '5 minutes'
        AND result->>'journal_revision'=?
      """,String.class,owner,revision,journalRevision(owner));
    if(!cached.isEmpty()){
      try{return json.readValue(cached.get(0),new com.fasterxml.jackson.core.type.TypeReference<Map<String,Object>>(){});}
      catch(com.fasterxml.jackson.core.JsonProcessingException ignored){/* Rebuild corrupted cache. */}
    }
    return refresh(owner);
  }

  public Map<String,Object> refresh(UUID owner){
    String revision=revision(owner);
    String journalRevision=journalRevision(owner);
    Instant now=Instant.now();
    LocalDate today=now.atZone(MarketCalendarService.IST).toLocalDate();
    // Read only this owner's holdings; market history is shared public evidence.
    // Ambiguous symbol matches are rejected unless all listings share an ISIN.
    var rows=jdbc.queryForList("""
      SELECT p.id,p.symbol,p.asset_type,p.quantity,p.last_price,p.quantity*p.average_cost AS invested,
        p.quantity*p.last_price AS market_value,p.price_as_of,
        (p.last_price IS NOT NULL AND p.last_price>=0 AND p.price_as_of IS NOT NULL
          AND p.price_as_of<=now()
          AND (now() AT TIME ZONE 'Asia/Kolkata')::date-(p.price_as_of AT TIME ZONE 'Asia/Kolkata')::date
            <= CASE WHEN p.asset_type='MUTUAL_FUND' THEN 7 ELSE 5 END) AS recorded_valuation_recent,
        i.exchange,i.id AS instrument_id,i.isin,s.scheme_code AS exact_scheme_code,s.category AS scheme_category,
        security.positive_security_observations,
        CASE WHEN p.asset_type='EQUITY' THEN eq.n ELSE mf.n END AS history_count,
        CASE WHEN p.asset_type='EQUITY' THEN eq.latest_date ELSE mf.latest_date END AS evidence_date,
        CASE WHEN p.asset_type='EQUITY' THEN eq.latest ELSE mf.latest END AS latest,
        CASE WHEN p.asset_type='EQUITY' THEN eq.prior ELSE mf.prior END AS prior,
        CASE WHEN p.asset_type='EQUITY' THEN eq.peak ELSE mf.peak END AS peak,
        eq.average AS average_close,eq.distinct_dates,eq.adjustments,eq.raw_count,
        mf.distinct_sources
      FROM personal_holdings p
      LEFT JOIN mutual_fund_schemes s ON p.asset_type='MUTUAL_FUND' AND p.symbol=s.scheme_code::text
      LEFT JOIN LATERAL (
        SELECT candidate.id,candidate.exchange,candidate.isin FROM (
          SELECT x.id,e.code AS exchange,x.isin,
                 count(*) OVER() AS matches,count(x.isin) OVER() AS known_isins,
                 min(x.isin) OVER() AS min_isin,max(x.isin) OVER() AS max_isin
          FROM instruments x JOIN exchanges e ON e.id=x.exchange_id
          WHERE p.asset_type='EQUITY' AND upper(x.symbol)=upper(p.symbol)
            AND x.active AND x.listing_status='ACTIVE' AND x.series='EQ'
            AND x.instrument_type IN ('EQ','EQUITY','STOCK') AND e.code IN ('NSE','BSE')
        ) candidate
        WHERE matches=1 OR (matches=known_isins AND min_isin=max_isin)
        ORDER BY CASE WHEN candidate.exchange='NSE' THEN 0 ELSE 1 END,candidate.id LIMIT 1
      ) i ON true
      LEFT JOIN LATERAL (
        SELECT string_agg(DISTINCT evidence,'; ' ORDER BY evidence) AS positive_security_observations
        FROM (
          SELECT d.exchange||' '||d.security_state||' (observed '||
            ((d.security_evidence_at AT TIME ZONE 'Asia/Kolkata')::date)::text||')' AS evidence
          FROM discovery_security_context d
          WHERE p.asset_type='EQUITY' AND d.isin=i.isin
            AND i.isin ~ '^INE[A-Z0-9]{8}[0-9]$'
            AND d.exchange IN ('NSE','BSE')
            AND d.security_state IN ('SUSPENDED_REPORTED','PCA','SME','RELIST','IPO')
            AND d.security_evidence_at<=now()
        ) observed
      ) security ON true
      LEFT JOIN LATERAL (
        SELECT count(*) n,count(DISTINCT trade_date) distinct_dates,
          count(DISTINCT adjustment_status) adjustments,
          count(*) FILTER(WHERE adjustment_status='RAW_UNADJUSTED') raw_count,
          max(trade_date) latest_date,max(close) FILTER(WHERE rn=1) latest,
          max(close) FILTER(WHERE rn=21) prior,max(close) peak,avg(close) average
        FROM (
          SELECT (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date AS trade_date,c.close,c.adjustment_status,
            row_number() OVER(ORDER BY c.candle_time DESC) rn
          FROM market_candles c
          WHERE c.instrument_id=i.id AND c.timeframe='1d' AND c.is_complete
            AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
            AND (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date < ?::date
          ORDER BY c.candle_time DESC LIMIT 50
        ) history
      ) eq ON true
      LEFT JOIN LATERAL (
        SELECT count(*) n,count(DISTINCT source_code) distinct_sources,
          max(nav_date) latest_date,max(nav) FILTER(WHERE rn=1) latest,
          max(nav) FILTER(WHERE rn=21) prior,max(nav) peak
        FROM (
          SELECT n.nav_date,n.nav,n.source_code,row_number() OVER(ORDER BY n.nav_date DESC) rn
          FROM mutual_fund_nav n
          WHERE n.scheme_code=CASE WHEN p.asset_type='MUTUAL_FUND' AND p.symbol ~ '^[0-9]{1,18}$'
            THEN p.symbol::bigint ELSE NULL END AND n.nav_date<=?::date
          ORDER BY n.nav_date DESC LIMIT 50
        ) history
      ) mf ON true
      WHERE p.user_id=? ORDER BY p.id
      """,today,today,owner);
    Map<String,Object> report=assess(rows,today,now);
    report.put("journal_revision",journalRevision);
    try{report.put("journal_lot_reconciliation",PortfolioJournalLots.collect(jdbc,owner,rows,today));}
    catch(org.springframework.dao.DataAccessException ex){
      report.put("journal_lot_reconciliation",Map.of("status","UNAVAILABLE_LOCAL_JOURNAL","holdings",List.of(),
        "reconciled_count",0,"notice","Local transaction journal could not be read. No tax-lot estimate."));
    }
    try{report.put("benchmark_risk_estimate",PortfolioBenchmarkEvidence.assessOwner(jdbc,owner,today));}
    catch(org.springframework.dao.DataAccessException ex){
      report.put("benchmark_risk_estimate",Map.of("status","UNAVAILABLE_LOCAL_EVIDENCE","attentionStatus","INSUFFICIENT_EVIDENCE"));
    }
    try{report.put("equity_correlation",PortfolioEquityCorrelation.collect(jdbc,rows,today));}
    catch(org.springframework.dao.DataAccessException ignored){report.put("equity_correlation",Map.of("status","UNAVAILABLE","notice","Local adjusted history could not be read."));}
    // Enrichment reads existing caches only. The scheduled review now produces
    // the same detailed digest that the authenticated dashboard consumes.
    var prior=json.createObjectNode();
    var priorRows=jdbc.queryForList("SELECT result::text FROM portfolio_review_snapshots WHERE user_id=?",String.class,owner);
    com.fasterxml.jackson.databind.JsonNode previous=prior;
    if(!priorRows.isEmpty())try{
      previous=json.readTree(priorRows.getFirst());
      if(previous==null)previous=prior;
    }catch(com.fasterxml.jackson.core.JsonProcessingException ignored){/* Invalid cache has no baseline. */}
    report=PortfolioThesisChanges.attach(thesis.enrich(report),previous,json,now);
    report=PortfolioFundThesisChanges.attach(report,previous,json,now);
    report=PortfolioOwnershipChanges.attach(report,previous,json,now);
    report.put("portfolio_level_risk",PortfolioLevelRisk.assess(report,json,today));
    report.put("sale_research",PortfolioSaleResearch.assess(rows,report,json,today));
    report.put("fund_exit_load_research",PortfolioFundExitLoad.assess(report,json,now));
    report.put("rebalancing_funding",PortfolioRebalancingFunding.assess(report));
    report.put("thesis_monitor_version","ANNUAL_DIRECTION_V1");
    try{
      jdbc.update("""
        INSERT INTO portfolio_review_snapshots(user_id,holdings_revision,generated_at,result)
        VALUES (?,?,?,?::jsonb) ON CONFLICT(user_id) DO UPDATE SET
        holdings_revision=EXCLUDED.holdings_revision,generated_at=EXCLUDED.generated_at,result=EXCLUDED.result
        WHERE portfolio_review_snapshots.generated_at<=EXCLUDED.generated_at
        """,owner,revision,java.sql.Timestamp.from(now),json.writeValueAsString(report));
    }catch(com.fasterxml.jackson.core.JsonProcessingException ex){
      throw new IllegalStateException("Portfolio review serialization failed",ex);
    }
    return report;
  }

  public void refreshDue(){
    // At most five owners per pass; no cross-user data is returned by the API.
    for(UUID owner:jdbc.queryForList("""
      SELECT u.id FROM atlas_users u LEFT JOIN portfolio_review_snapshots s ON s.user_id=u.id
      WHERE EXISTS(SELECT 1 FROM personal_holdings h WHERE h.user_id=u.id)
        AND (s.generated_at IS NULL OR s.generated_at<now()-interval '5 minutes')
      ORDER BY s.generated_at ASC NULLS FIRST,u.id LIMIT 5
      """,UUID.class)){
      try{refresh(owner);}catch(org.springframework.dao.DataAccessException|IllegalStateException ex){
        // Isolate failed owners; next pass retries. Never log holdings or credentials.
      }
    }
  }

  static Map<String,Object> assess(List<Map<String,Object>> rows,LocalDate today,Instant now){
    BigDecimal total=rows.stream().map(r->decimal(r,"market_value")).filter(Objects::nonNull)
      .reduce(BigDecimal.ZERO,BigDecimal::add);
    List<Map<String,Object>> assessments=new ArrayList<>();
    int attention=0,gaps=0;
    for(var r:rows){
      boolean equity="EQUITY".equals(r.get("asset_type"));
      List<String> findings=new ArrayList<>(),missing=new ArrayList<>();
      BigDecimal value=decimal(r,"market_value"),cost=decimal(r,"invested");
      Double weight=percentage(value,total),returnPct=cost!=null&&value!=null?percentage(value.subtract(cost),cost):null;
      if(value==null)missing.add("No recorded valuation.");
      else {
        missing.add("Recorded valuation is not independently verified as a live price.");
        if(weight!=null&&weight>25)findings.add("Position exceeds 25% of recorded priced holdings; review concentration.");
        if(returnPct!=null&&returnPct<=-10)findings.add("Recorded value is at least 10% below cost; reassess the investment thesis rather than assume recovery.");
      }
      long count=number(r,"history_count");
      LocalDate observed=date(r.get("evidence_date"));
      long age=observed==null?Long.MAX_VALUE:java.time.temporal.ChronoUnit.DAYS.between(observed,today);
      boolean valid=count>=21&&age>=0&&age<=5;
      if(equity){
        if(r.get("instrument_id")==null){missing.add("Stock mapping missing or ambiguous.");valid=false;}
        if(number(r,"distinct_dates")!=count||number(r,"adjustments")!=1){missing.add("Daily history has duplicate dates or mixed adjustment status.");valid=false;}
        if(number(r,"raw_count")>0)missing.add("Raw prices may be distorted by corporate actions.");
        if(r.get("positive_security_observations") instanceof String positive&&!positive.isBlank()){
          findings.add("Reported listing cautions for this company: "+positive+
            ". Verify the relevant exchange; retained suspension evidence may be old and another venue is not automatically restricted.");
        }
        missing.add("Complete current NSE/BSE restriction clearance is not established by available listing classifications.");
        missing.add("Current fundamentals, valuation, institutional activity and news have not been verified in this review.");
      }else{
        if(number(r,"distinct_sources")!=1){missing.add("NAV history lacks a consistent source.");valid=false;}
        missing.add("Fund holdings, benchmark, fees and official risk classification have not been verified in this review.");
      }
      if(count<21)missing.add("At least 21 dated observations are needed for historical change.");
      if(age<0||age>5)missing.add("Historical observations are missing, stale or future-dated.");
      BigDecimal latest=decimal(r,"latest"),prior=decimal(r,"prior"),peak=decimal(r,"peak");
      Double momentum=valid&&latest!=null&&prior!=null?percentage(latest.subtract(prior),prior):null;
      Double drawdown=valid&&latest!=null&&peak!=null?percentage(latest.subtract(peak),peak):null;
      if(momentum!=null&&momentum<=-5)findings.add("Latest observed value fell at least 5% over 20 observations.");
      if(drawdown!=null&&drawdown<=-10)findings.add("Latest observed value is at least 10% below its recent observed peak.");
      BigDecimal avg=decimal(r,"average_close");
      if(equity&&valid&&count>=50&&latest!=null&&avg!=null&&latest.compareTo(avg)<0)
        findings.add("Latest daily close is below its 50-observation average.");
      String status=!findings.isEmpty()?"REVIEW_REQUIRED":valid?"MONITOR":"EVIDENCE_GAP";
      if(!findings.isEmpty())attention++;
      if(!valid||value==null)gaps++;
      Map<String,Object> item=new LinkedHashMap<>();
      item.put("id",r.get("id"));item.put("symbol",r.get("symbol"));item.put("asset_type",r.get("asset_type"));
      item.put("exchange",r.get("exchange"));item.put("isin",r.get("isin"));item.put("status",status);item.put("weight_percent",weight);
      item.put("recorded_valuation_recent",Boolean.TRUE.equals(r.get("recorded_valuation_recent")));
      item.put("recorded_market_value",value);item.put("exact_scheme_code",r.get("exact_scheme_code"));item.put("scheme_category",r.get("scheme_category"));item.put("recorded_return_percent",returnPct);item.put("evidence_date",observed==null?null:observed.toString());
      item.put("history_count",count);item.put("change_20_observations_percent",momentum);
      item.put("recent_peak_change_percent",drawdown);item.put("findings",findings);item.put("missing_evidence",missing);
      assessments.add(item);
    }
    assessments.sort(Comparator.comparingInt(r->"REVIEW_REQUIRED".equals(r.get("status"))?0:"EVIDENCE_GAP".equals(r.get("status"))?1:2));
    Map<String,Object> out=new LinkedHashMap<>();
    out.put("generated_at",now.toString());out.put("holding_count",rows.size());
    out.put("attention_count",attention);out.put("data_gap_count",gaps);out.put("holdings",assessments);
    out.put("methodology","PORTFOLIO_REVIEW_V1");out.put("notice","Local recorded valuations and dated historical observations only. No buy/sell verdict, live price assurance, or complete investment thesis.");
    return out;
  }

  private static BigDecimal decimal(Map<String,Object> row,String key){
    Object value=row.get(key);return value instanceof BigDecimal d?d:null;
  }
  private static long number(Map<String,Object> row,String key){
    return row.get(key) instanceof Number n?n.longValue():0;
  }
  private static LocalDate date(Object value){
    return value instanceof java.sql.Date d?d.toLocalDate():value instanceof LocalDate d?d:null;
  }
  private static Double percentage(BigDecimal numerator,BigDecimal denominator){
    if(numerator==null||denominator==null||denominator.signum()<=0)return null;
    return numerator.multiply(BigDecimal.valueOf(100)).divide(denominator,2,RoundingMode.HALF_UP).doubleValue();
  }
}
