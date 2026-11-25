package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import static com.trading.market.PortfolioFlowAdjustedPerformance.*;

public final class PortfolioBenchmarkEvidence {
  private PortfolioBenchmarkEvidence(){}
  public static PortfolioBenchmarkRisk.Assessment assessOwner(JdbcTemplate jdbc,UUID owner,LocalDate today){
    var rows=jdbc.queryForList("""
      SELECT valuation_date,total_value,priced_positions,unpriced_positions
      FROM portfolio_valuation_snapshots WHERE user_id=? AND valuation_date BETWEEN ? AND ?
      ORDER BY valuation_date
      """,owner,today.minusDays(98),today);
    var observations=rows.stream().map(r->{
      BigDecimal value=(BigDecimal)r.get("total_value");
      boolean complete=((Number)r.get("priced_positions")).longValue()>0
        &&((Number)r.get("unpriced_positions")).longValue()==0&&value!=null&&value.signum()>=0
        &&Double.isFinite(value.doubleValue());
      return new Observation(day(r.get("valuation_date")),value,complete);
    }).toList();
    if(observations.isEmpty())return PortfolioBenchmarkRisk.assess(observations,List.of(),List.of(),today);
    LocalDate end=observations.getLast().date();
    var flows=jdbc.queryForList("""
      SELECT transaction_date,transaction_type,cash_amount FROM portfolio_transactions
      WHERE user_id=? AND transaction_date>? AND transaction_date<=?
        AND transaction_type IN ('DEPOSIT','WITHDRAWAL','DIVIDEND','FEE')
      ORDER BY transaction_date
      """,owner,end.minusWeeks(13),end).stream().map(r->{
        BigDecimal cash=(BigDecimal)r.get("cash_amount");
        String type=(String)r.get("transaction_type");
        return new Flow(day(r.get("transaction_date")),
          "DEPOSIT".equals(type)||"FEE".equals(type)?cash:cash.negate());
      }).toList();
    return PortfolioBenchmarkRisk.assess(observations,flows,points(jdbc,end,today),today);
  }

  public static List<PortfolioRollingPerformance.BenchmarkPoint> points(JdbcTemplate jdbc,LocalDate terminal,LocalDate today){
    // Historical reference only; never use the live index strip or a fund as an index substitute.
    var rows=jdbc.queryForList("""
      WITH candidate AS (
        SELECT i.id,i.exchange_id FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
        WHERE e.code='NSE' AND i.active AND i.listing_status='ACTIVE'
          AND i.instrument_type='INDEX' AND i.exchange_token='NSE_INDEX|Nifty 50'
      )
      SELECT (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date AS trade_date,c.close,
        ds.source_code,
        (c.is_complete AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
          AND c.adjustment_status='RAW_UNADJUSTED' AND ds.enabled
          AND EXISTS(SELECT 1 FROM market_sessions s WHERE s.exchange_id=i.exchange_id
            AND s.session_date=(c.candle_time AT TIME ZONE 'Asia/Kolkata')::date
            AND s.session_type='REGULAR' AND s.is_trading_day AND s.close_time=c.candle_time)
          AND c.candle_time<=now()) AS eligible
      FROM candidate i JOIN market_candles c ON c.instrument_id=i.id
      LEFT JOIN data_sources ds ON ds.id=c.source_id
      WHERE (SELECT count(*) FROM candidate)=1 AND c.timeframe='1d'
        AND (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date BETWEEN ? AND ?
        AND (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date<=?
      ORDER BY c.candle_time
      """,terminal.minusDays(365),terminal,today);
    return rows.stream().map(row->new PortfolioRollingPerformance.BenchmarkPoint(
      day(row.get("trade_date")),(BigDecimal)row.get("close"),(String)row.get("source_code"),
      Boolean.TRUE.equals(row.get("eligible")))).toList();
  }

  private static LocalDate day(Object value){
    return value instanceof java.sql.Date d?d.toLocalDate():(LocalDate)value;
  }
}
