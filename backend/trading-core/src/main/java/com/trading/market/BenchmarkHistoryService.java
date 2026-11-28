package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/** Explicit, bounded public index history. Never accepts a private vault token or arbitrary key. */
@Service
public class BenchmarkHistoryService {
  public static final String KEY="NSE_INDEX|Nifty 50";
  // Only exact public price-index keys; no caller-supplied provider path.
  // Bank is documented by Upstox; other named indices require live key acceptance.
  public static final List<String> SECTOR_KEYS=List.of("NSE_INDEX|Nifty Bank","NSE_INDEX|Nifty IT",
      "NSE_INDEX|Nifty Auto","NSE_INDEX|Nifty Pharma","NSE_INDEX|Nifty FMCG","NSE_INDEX|Nifty Metal");
  public static boolean allowed(String key){return KEY.equals(key)||SECTOR_KEYS.contains(key);}
  static String historyUrl(String key,LocalDate from,LocalDate to){
    if(!allowed(key))throw new IllegalArgumentException("Unsupported benchmark");
    return "https://api.upstox.com/v3/historical-candle/"+java.net.URLEncoder.encode(key,java.nio.charset.StandardCharsets.UTF_8).replace("+","%20")+"/days/1/"+to+"/"+from;
  }
  private final JdbcTemplate jdbc;
  private final FeedHttp http;
  private final TransactionTemplate transactions;
  private final ObjectMapper json=new ObjectMapper();
  public BenchmarkHistoryService(JdbcTemplate jdbc,FeedHttp http,TransactionTemplate transactions){
    this.jdbc=jdbc;this.http=http;this.transactions=transactions;
  }
  record Candle(LocalDate date,BigDecimal open,BigDecimal high,BigDecimal low,BigDecimal close,long volume){}

  Long ensureIndex(){return ensureIndex(KEY);}
  Long ensureIndex(String key){
    if(!allowed(key))throw new IllegalArgumentException("Unsupported benchmark");
    String name=key.substring("NSE_INDEX|".length());
    String symbol=name.toUpperCase(Locale.ROOT).replace(" ","");
    // Never convert an existing equity or unrelated instrument into an index.
    jdbc.update("""
      INSERT INTO instruments(exchange_id,symbol,series,security_name,instrument_type,exchange_token,
        listing_status,active,source,source_revision,updated_at)
      SELECT e.id,?,'INDEX',?,'INDEX',?,'ACTIVE',true,'UPSTOX','UPSTOX_INDEX_KEY',now()
      FROM exchanges e WHERE e.code='NSE'
        AND NOT EXISTS(SELECT 1 FROM instruments i WHERE i.exchange_id=e.id AND i.exchange_token=?)
      ON CONFLICT DO NOTHING
      """,symbol,name.toUpperCase(Locale.ROOT),key,key);
    var ids=jdbc.query("""
      SELECT i.id FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
      WHERE e.code='NSE' AND i.active AND i.listing_status='ACTIVE'
        AND i.instrument_type='INDEX' AND i.exchange_token=?
      """,(rs,n)->rs.getLong(1),key);
    return ids.size()==1?ids.getFirst():null;
  }

  static List<Candle> parse(JsonNode body,LocalDate from,LocalDate to){
    JsonNode candles=body.path("data").path("candles");
    if(!"success".equals(body.path("status").asText())||!candles.isArray()||candles.isEmpty()||candles.size()>400)
      throw new IllegalArgumentException("Invalid index candle response");
    List<Candle> result=new ArrayList<>();
    Set<LocalDate> dates=new HashSet<>();
    for(JsonNode row:candles){
      if(!row.isArray()||row.size()<6||!row.get(0).isTextual())throw new IllegalArgumentException("Invalid index candle");
      LocalDate date=OffsetDateTime.parse(row.get(0).asText()).atZoneSameInstant(MarketCalendarService.IST).toLocalDate();
      if(date.isBefore(from)||date.isAfter(to)||!dates.add(date))throw new IllegalArgumentException("Invalid or duplicate index date");
      for(int j=1;j<=4;j++)if(!row.get(j).isNumber())throw new IllegalArgumentException("Invalid index OHLC");
      BigDecimal open=row.get(1).decimalValue(),high=row.get(2).decimalValue(),low=row.get(3).decimalValue(),close=row.get(4).decimalValue();
      if(open.signum()<=0||high.signum()<=0||low.signum()<=0||close.signum()<=0||
          high.compareTo(open)<0||high.compareTo(close)<0||high.compareTo(low)<0||
          low.compareTo(open)>0||low.compareTo(close)>0||!row.get(5).isIntegralNumber()||
          !row.get(5).canConvertToLong()||row.get(5).asLong()<0)
        throw new IllegalArgumentException("Invalid index OHLC or volume");
      result.add(new Candle(date,open,high,low,close,row.get(5).asLong()));
    }
    return result;
  }

  public int refresh(long instrument,String token,LocalDate from,LocalDate to)throws Exception{
    return refresh(instrument,KEY,token,from,to);
  }
  int refresh(long instrument,String key,String token,LocalDate from,LocalDate to)throws Exception{
    if(!allowed(key))throw new IllegalArgumentException("Unsupported benchmark");
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    if(token==null||token.isBlank()||from.isAfter(to)||from.isBefore(to.minusDays(470))||!to.isBefore(today))
      throw new IllegalArgumentException("Invalid completed index history request");
    var sources=jdbc.query("SELECT id FROM data_sources WHERE source_code='UPSTOX' AND enabled",(rs,n)->rs.getLong(1));
    if(sources.size()!=1)throw new IllegalStateException("Index source not enabled");
    long source=sources.getFirst();
    String url=historyUrl(key,from,to);
    List<Candle> candles=parse(json.readTree(http.text(url,token,2_000_000)),from,to);
    Integer count=transactions.execute(status->{
      var exact=jdbc.queryForObject("""
        SELECT count(*) FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
        WHERE e.code='NSE' AND i.active AND i.listing_status='ACTIVE'
          AND i.instrument_type='INDEX' AND i.exchange_token=?
        """,Integer.class,key);
      if(!Integer.valueOf(1).equals(exact))throw new IllegalStateException("Ambiguous index identity");
      var identity=jdbc.queryForObject("""
        SELECT count(*) FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
        WHERE i.id=? AND e.code='NSE' AND i.active AND i.listing_status='ACTIVE'
          AND i.instrument_type='INDEX' AND i.exchange_token=?
        """,Integer.class,instrument,key);
      if(!Integer.valueOf(1).equals(identity))throw new IllegalStateException("Index identity changed");
      UUID run=jdbc.queryForObject("""
        INSERT INTO ingestion_runs(source_id,job_name,status,started_at,source_revision)
        VALUES (?,'upstox-benchmark-history','RUNNING',now(),?) RETURNING id
        """,UUID.class,source,"UPSTOX_INDEX:"+from+":"+to);
      int written=0,skipped=0;
      for(Candle candle:candles){
        // Provider timestamps label the candle start. The date must match
        // exactly one known regular session; unknown dates are never guessed.
        var closes=jdbc.query("""
          SELECT s.close_time FROM market_sessions s JOIN instruments i ON i.exchange_id=s.exchange_id
          WHERE i.id=? AND s.session_date=? AND s.session_type='REGULAR' AND s.is_trading_day
            AND s.open_time IS NOT NULL AND s.close_time IS NOT NULL AND s.open_time<s.close_time
            AND (s.close_time AT TIME ZONE 'Asia/Kolkata')::date=s.session_date AND s.close_time<=now()
            AND NOT EXISTS(SELECT 1 FROM market_sessions x WHERE x.exchange_id=s.exchange_id
              AND x.session_date=s.session_date AND x.is_trading_day AND x.session_type<>'REGULAR')
          """,(rs,n)->rs.getTimestamp(1),instrument,candle.date());
        if(closes.size()!=1){skipped++;continue;}
        int changed=jdbc.update("""
          INSERT INTO market_candles(instrument_id,timeframe,candle_time,source_id,ingestion_run_id,
            open,high,low,close,volume,is_complete,quality_status,adjustment_status)
          VALUES (?,'1d',?,?,?,?,?,?,?,?,true,'PROVIDER_VALIDATED','RAW_UNADJUSTED')
          ON CONFLICT(instrument_id,timeframe,candle_time) DO UPDATE SET
            open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,
            volume=EXCLUDED.volume,ingestion_run_id=EXCLUDED.ingestion_run_id,
            quality_status=EXCLUDED.quality_status,is_complete=true,received_at=now()
          WHERE market_candles.source_id=EXCLUDED.source_id AND market_candles.adjustment_status='RAW_UNADJUSTED'
          """,instrument,closes.getFirst(),source,run,candle.open(),candle.high(),candle.low(),candle.close(),candle.volume());
        written+=changed;if(changed==0)skipped++;
      }
      jdbc.update("UPDATE ingestion_runs SET status=?,finished_at=now(),records_seen=?,records_written=?,failure_count=? WHERE id=?",
        written>0?"SUCCESS":"FAILED",candles.size(),written,skipped,run);
      if(written>0)jdbc.update("""
        INSERT INTO instrument_source_freshness(instrument_id,source_id,last_synced_at,latest_candle_at)
        VALUES (?,?,now(),(SELECT max(candle_time) FROM market_candles WHERE instrument_id=? AND source_id=? AND timeframe='1d'))
        ON CONFLICT(instrument_id,source_id) DO UPDATE SET last_synced_at=now(),latest_candle_at=EXCLUDED.latest_candle_at
        """,instrument,source,instrument,source);
      return written;
    });
    return count==null?0:count;
  }
}
