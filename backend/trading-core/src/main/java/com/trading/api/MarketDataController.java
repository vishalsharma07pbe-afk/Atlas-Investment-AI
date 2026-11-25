package com.trading.api;

import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/market-data")
public class MarketDataController {
  private final JdbcTemplate jdbc;
  public MarketDataController(JdbcTemplate jdbc){this.jdbc=jdbc;}

  @GetMapping("/instruments/{id}/candles")
  @org.springframework.transaction.annotation.Transactional(readOnly=true,isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
  public Map<String,Object> candles(@PathVariable long id,@RequestParam(defaultValue="500") int limit){
    int safe=Math.max(1,Math.min(limit,2000));
    List<Map<String,Object>> instrument=jdbc.queryForList("""
      SELECT i.id,e.code exchange,i.symbol,i.series,i.isin,i.security_name,i.listing_status,i.active,i.instrument_type,
        to_char(i.listed_on,'YYYY-MM-DD') AS listed_on,to_char(i.delisted_on,'YYYY-MM-DD') AS delisted_on,
        i.source AS registry_source,i.source_revision AS registry_revision,
        to_char((now() AT TIME ZONE 'Asia/Kolkata')::date-1,'YYYY-MM-DD') AS action_context_through,
        to_char(a.latest_action_date,'YYYY-MM-DD') AS latest_action_date,
        a.corporate_action_context
      FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
      CROSS JOIN LATERAL (
        SELECT max(x.ex_date) latest_action_date,
          coalesce(jsonb_agg(jsonb_build_object('action_type',x.action_type,'ex_date',x.ex_date,
            'ratio',x.ratio::text,'cash_amount',x.cash_amount::text,'ratio_basis',x.raw_payload->>'ratio_basis',
            'isin',x.raw_payload->>'isin','source_revision',x.source_revision)
            ORDER BY x.ex_date DESC,x.action_type,x.source_revision),'[]'::jsonb)::text corporate_action_context
        FROM (SELECT ca.action_type,ca.ex_date,ca.ratio,ca.cash_amount,ca.raw_payload,ca.source_revision
          FROM corporate_actions ca WHERE ca.instrument_id=i.id
            AND ca.ex_date < (now() AT TIME ZONE 'Asia/Kolkata')::date
          ORDER BY ca.ex_date DESC,ca.action_type,ca.source_revision LIMIT 33) x
      ) a WHERE i.id=?
      """,id);
    if(instrument.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Instrument not found");
    List<Map<String,Object>> rows=jdbc.queryForList("""
      SELECT * FROM (SELECT (c.candle_time AT TIME ZONE e.timezone)::date trade_date,c.candle_time,c.open,c.high,c.low,c.close,c.volume,
      c.adjustment_status,c.quality_status,c.revision,c.source_revision,ds.source_code,c.received_at
      FROM market_candles c JOIN instruments i ON i.id=c.instrument_id JOIN exchanges e ON e.id=i.exchange_id
      LEFT JOIN data_sources ds ON ds.id=c.source_id WHERE c.instrument_id=? AND c.timeframe='1d' AND c.is_complete
      AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
      ORDER BY c.candle_time DESC LIMIT ?) x ORDER BY candle_time
      """,id,safe);
    Map<String,Object> out=new LinkedHashMap<>();out.put("instrument",instrument.get(0));out.put("timeframe","1d");out.put("candles",rows);
    out.put("count",rows.size());out.put("latest",rows.isEmpty()?null:rows.get(rows.size()-1).get("trade_date"));
    out.put("notice","Validated daily records only. Provider records retain their source and adjustment status; daily candles are not live quotes.");return out;
  }

  @GetMapping("/instruments/{id}/freshness")
  public Map<String,Object> freshness(@PathVariable long id){
    if(Boolean.FALSE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM instruments WHERE id=?)",Boolean.class,id)))throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Instrument not found");
    return jdbc.queryForMap("""
      SELECT count(*) candle_count,min(c.candle_time) first_candle,max(c.candle_time) latest_candle,max(c.received_at) last_received,
      count(*) FILTER(WHERE c.adjustment_status='RAW_UNADJUSTED') raw_unadjusted_count,
      count(*) FILTER(WHERE c.adjustment_status='ADJUSTED') adjusted_count,
      count(DISTINCT c.source_id) source_count
      FROM market_candles c WHERE c.instrument_id=? AND c.timeframe='1d' AND c.is_complete
      """,id);
  }
}
