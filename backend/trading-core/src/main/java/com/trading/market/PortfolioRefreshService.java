package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Shared read-only provider refresh for authenticated requests and background work.
 * Every write uses the explicit holding owner; no synthetic authentication context.
 */
@Service
public class PortfolioRefreshService {
  private final JdbcTemplate jdbc;
  private final UpstoxFeedService upstox;

  public PortfolioRefreshService(JdbcTemplate jdbc,UpstoxFeedService upstox){
    this.jdbc=jdbc;this.upstox=upstox;
  }

  public Map<String,Object> refreshUser(UUID user,boolean includeHistory){
    return refresh(jdbc.queryForList("""
      SELECT id,user_id,symbol,asset_type FROM personal_holdings
      WHERE user_id=? ORDER BY asset_type,symbol LIMIT 200
      """,user),includeHistory);
  }

  /** At most ten holdings per pass, oldest attempts first. Mark attempts before
   * provider access so failures cannot starve other holdings or cause tight loops.
   * This is intended for the single local backend instance.
   */
  public Map<String,Object> refreshDue(int requestedLimit){
    int limit=Math.max(1,Math.min(10,requestedLimit));
    List<Map<String,Object>> rows=jdbc.queryForList("""
      WITH due AS (
        SELECT h.id FROM personal_holdings h
        WHERE (h.last_auto_refresh_attempt_at IS NULL
          OR h.last_auto_refresh_attempt_at < now()-interval '15 minutes')
          AND (h.asset_type='MUTUAL_FUND' OR EXISTS(
            SELECT 1 FROM broker_credentials b WHERE b.user_id=h.user_id
            AND b.broker_name='UPSTOX' AND b.token_expires_at>now()))
        ORDER BY h.last_auto_refresh_attempt_at ASC NULLS FIRST,h.id
        LIMIT ? FOR UPDATE SKIP LOCKED
      )
      UPDATE personal_holdings h SET last_auto_refresh_attempt_at=now()
      FROM due WHERE h.id=due.id RETURNING h.id,h.user_id,h.symbol,h.asset_type
      """,limit);
    return refresh(rows,true);
  }

  private Map<String,Object> refresh(List<Map<String,Object>> rows,boolean includeHistory){
    int updated=0,historySynced=0;
    List<Map<String,String>> skipped=new ArrayList<>();
    for(Map<String,Object> row:rows){
      long id=((Number)row.get("id")).longValue();
      UUID user=(UUID)row.get("user_id");
      String symbol=String.valueOf(row.get("symbol"));
      try{
        if("EQUITY".equals(row.get("asset_type"))){
          List<String> keys=jdbc.queryForList("""
            SELECT instrument_key FROM upstox_instrument_map
            WHERE upper(trading_symbol)=upper(?)
            ORDER BY CASE WHEN exchange_code='NSE' THEN 0 ELSE 1 END,
              CASE WHEN instrument_type='EQ' THEN 0 ELSE 1 END,instrument_key LIMIT 1
            """,String.class,symbol);
          if(keys.isEmpty()){skipped.add(issue(symbol,"INSTRUMENT_NOT_MAPPED"));continue;}
          String key=keys.get(0);
          JsonNode quote=upstox.quote(user,key);
          if(!quote.path("ltp").isNumber()||quote.path("ltp").decimalValue().signum()<=0)
            throw new IllegalStateException("INVALID_QUOTE");
          BigDecimal price=quote.path("ltp").decimalValue();
          BigDecimal previous=quote.path("previous_close").isNumber()?quote.path("previous_close").decimalValue():null;
          updated+=jdbc.update("""
            UPDATE personal_holdings SET last_price=?,previous_close=?,price_as_of=now(),updated_at=now()
            WHERE id=? AND user_id=? AND symbol=? AND asset_type='EQUITY'
            """,price,previous,id,user,symbol);
          if(includeHistory){
            try{
              LocalDate today=LocalDate.now(MarketCalendarService.IST);
              // Never mark a possibly unfinished current-day candle complete.
              LocalDate end=today.minusDays(1);
              Map<String,Object> history=jdbc.queryForMap("""
                SELECT count(c.*) candle_count,max(c.candle_time)::date latest_date
                FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
                LEFT JOIN market_candles c ON c.instrument_id=i.id AND c.timeframe='1d'
                  AND c.is_complete AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
                JOIN upstox_instrument_map m ON m.exchange_code=e.code AND m.trading_symbol=i.symbol
                WHERE m.instrument_key=? GROUP BY i.id
                """,key);
              long count=((Number)history.get("candle_count")).longValue();
              Object raw=history.get("latest_date");
              LocalDate latest=raw instanceof java.sql.Date d?d.toLocalDate():raw instanceof LocalDate d?d:null;
              if(count<21||latest==null||latest.isBefore(today.minusDays(5)))
                historySynced+=upstox.dailyCandles(user,key,today.minusMonths(6),end);
            }catch(Exception ex){skipped.add(issue(symbol,"HISTORY_SYNC_FAILED"));}
          }
        }else if(symbol.matches("[0-9]{1,18}")){
          List<Map<String,Object>> nav=jdbc.queryForList("""
            SELECT nav,nav_date FROM mutual_fund_nav WHERE scheme_code=?
            ORDER BY nav_date DESC LIMIT 2
            """,Long.parseLong(symbol));
          if(nav.isEmpty()){skipped.add(issue(symbol,"NAV_NOT_AVAILABLE"));continue;}
          Object previous=nav.size()>1?nav.get(1).get("nav"):null;
          updated+=jdbc.update("""
            UPDATE personal_holdings SET last_price=?,previous_close=?,price_as_of=?::date,updated_at=now()
            WHERE id=? AND user_id=? AND symbol=? AND asset_type='MUTUAL_FUND'
            AND (price_as_of IS NULL OR price_as_of::date<=?::date)
            """,nav.get(0).get("nav"),previous,nav.get(0).get("nav_date"),id,user,symbol,nav.get(0).get("nav_date"));
        }else skipped.add(issue(symbol,"SCHEME_CODE_REQUIRED"));
      }catch(Exception ex){
        // Never expose arbitrary exception messages, URLs, or provider credentials.
        String reason="Upstox credential unavailable".equals(ex.getMessage())?
          "Upstox credential unavailable":"PROVIDER_REFRESH_FAILED";
        skipped.add(issue(symbol,reason));
      }
    }
    Map<String,Object> result=new LinkedHashMap<>();
    result.put("updated",updated);result.put("history_synced",historySynced);
    result.put("total",rows.size());result.put("skipped",skipped);
    result.put("refreshed_at",Instant.now());
    return result;
  }

  private static Map<String,String> issue(String symbol,String reason){
    return Map.of("symbol",symbol,"reason",reason);
  }
}
